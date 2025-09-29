import os
import sys
import json
import yaml
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Publication:
    """Data class for storing publication information"""
    title: str
    authors: List[str]
    journal: str = ""
    year: int = 0
    volume: str = ""
    pages: str = ""
    doi: str = ""
    arxiv_id: str = ""
    url: str = ""
    abstract: str = ""
    type: str = "journal"  # journal, preprint, conference, book
    venue: str = ""
    pdf_url: str = ""
    bibtex: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    def get_citation_key(self) -> str:
        """Generate a unique citation key for this publication"""
        first_author = self.authors[0].split()[-1].lower() if self.authors else "unknown"
        title_words = self.title.lower().split()[:3]
        key_parts = [first_author, str(self.year)] + title_words
        return "_".join(re.sub(r'[^\w]', '', part) for part in key_parts if part)
    
    def format_authors(self, highlight_author: str = "M. Avesani") -> str:
        """Format authors list, highlighting the specified author"""
        formatted_authors = []
        for author in self.authors:
            if highlight_author.lower() in author.lower():
                formatted_authors.append(f"**{author}**")
            else:
                formatted_authors.append(author)
        return ", ".join(formatted_authors)
    
    def generate_markdown_content(self, highlight_author: str = "M. Avesani") -> str:
        """Generate markdown content for Jekyll"""
        content = f"""---
title: "{self.title}"
collection: publications
permalink: /publication/{self.get_citation_key()}
excerpt: '{self.abstract[:200]}...' if len(self.abstract) > 200 else self.abstract
date: {self.year}-01-01
venue: '{self.venue or self.journal}'
paperurl: '{self.url}'
citation: '{self.format_citation()}'
---

{self.abstract}

**Authors:** {self.format_authors(highlight_author)}

"""
        
        # Add links
        links = []
        if self.url:
            links.append(f"[Paper]({self.url}){{: .btn .btn--info}}")
        if self.arxiv_id:
            arxiv_url = f"https://arxiv.org/abs/{self.arxiv_id}"
            links.append(f"[ArXiv]({arxiv_url}){{: .btn .btn--info}}")
        if self.pdf_url:
            links.append(f"[PDF]({self.pdf_url}){{: .btn .btn--info}}")
        if self.doi:
            doi_url = f"https://doi.org/{self.doi}"
            links.append(f"[DOI]({doi_url}){{: .btn .btn--info}}")
            
        if links:
            content += "\n" + " ".join(links) + "\n"
            
        if self.bibtex:
            content += f"\n## BibTeX\n\n```bibtex\n{self.bibtex}\n```\n"
            
        return content
    
    def format_citation(self) -> str:
        """Format citation string"""
        authors_str = self.format_authors()
        if len(authors_str) > 100:
            authors_str = authors_str[:97] + "..."
            
        citation_parts = [authors_str]
        citation_parts.append(f'"{self.title}"')
        
        if self.journal:
            citation_parts.append(self.journal)
        elif self.venue:
            citation_parts.append(self.venue)
            
        if self.volume:
            citation_parts.append(f"vol. {self.volume}")
        if self.pages:
            citation_parts.append(f"pp. {self.pages}")
        if self.year:
            citation_parts.append(f"({self.year})")
            
        return ", ".join(citation_parts) + "."

class PublicationNormalizer:
    """Normalize publications from different sources into a standard format"""
    
    @staticmethod
    def normalize_author_name(name: str) -> str:
        """Normalize author names to a consistent format"""
        # Remove extra whitespace and normalize
        name = re.sub(r'\s+', ' ', name.strip())
        
        # Handle different name formats
        if ',' in name:
            # "Last, First Middle" format
            parts = name.split(',', 1)
            if len(parts) == 2:
                last = parts[0].strip()
                first_middle = parts[1].strip()
                # Convert to "First Middle Last" format
                name = f"{first_middle} {last}"
        
        return name
    
    @staticmethod
    def extract_year_from_date(date_str: str) -> int:
        """Extract year from various date formats"""
        if not date_str:
            return 0
            
        # Try to extract 4-digit year
        year_match = re.search(r'\b(19|20)\d{2}\b', str(date_str))
        if year_match:
            return int(year_match.group())
        
        return 0
    
    @staticmethod
    def clean_title(title: str) -> str:
        """Clean and normalize title"""
        if not title:
            return ""
            
        # Remove extra whitespace
        title = re.sub(r'\s+', ' ', title.strip())
        
        # Remove common prefixes/suffixes that might be artifacts
        title = re.sub(r'^(Title:|Abstract:)\s*', '', title, flags=re.IGNORECASE)
        
        return title
    
    @staticmethod
    def detect_publication_type(venue: str, journal: str, arxiv_id: str) -> str:
        """Detect publication type based on venue/journal information"""
        venue_lower = (venue or "").lower()
        journal_lower = (journal or "").lower()
        
        if arxiv_id and not journal:
            return "preprint"
        elif any(word in venue_lower or word in journal_lower 
                for word in ["conference", "proceedings", "workshop", "symposium"]):
            return "conference"
        elif any(word in venue_lower or word in journal_lower 
                for word in ["journal", "letters", "review", "transactions"]):
            return "journal"
        elif any(word in venue_lower or word in journal_lower 
                for word in ["book", "chapter"]):
            return "book"
        else:
            return "journal"  # default

class PublicationDeduplicator:
    """Remove duplicate publications based on various criteria"""
    
    @staticmethod
    def compute_similarity_score(pub1: Publication, pub2: Publication) -> float:
        """Compute similarity score between two publications"""
        score = 0.0
        
        # Title similarity (most important)
        title1 = pub1.title.lower().strip()
        title2 = pub2.title.lower().strip()
        
        if title1 == title2:
            score += 0.5
        elif title1 in title2 or title2 in title1:
            score += 0.3
        else:
            # Simple word overlap
            words1 = set(title1.split())
            words2 = set(title2.split())
            if words1 and words2:
                overlap = len(words1.intersection(words2)) / len(words1.union(words2))
                score += overlap * 0.3
        
        # Author similarity
        authors1 = set(author.lower().strip() for author in pub1.authors)
        authors2 = set(author.lower().strip() for author in pub2.authors)
        if authors1 and authors2:
            author_overlap = len(authors1.intersection(authors2)) / len(authors1.union(authors2))
            score += author_overlap * 0.2
        
        # Year similarity
        if pub1.year == pub2.year and pub1.year > 0:
            score += 0.1
        
        # DOI/ArXiv ID exact match
        if pub1.doi and pub2.doi and pub1.doi == pub2.doi:
            score += 0.2
        if pub1.arxiv_id and pub2.arxiv_id and pub1.arxiv_id == pub2.arxiv_id:
            score += 0.2
            
        return score
    
    @staticmethod
    def deduplicate_publications(publications: List[Publication], 
                               threshold: float = 0.8) -> List[Publication]:
        """Remove duplicate publications based on similarity threshold"""
        if not publications:
            return []
            
        deduplicated = []
        
        for pub in publications:
            is_duplicate = False
            
            for existing_pub in deduplicated:
                similarity = PublicationDeduplicator.compute_similarity_score(pub, existing_pub)
                
                if similarity >= threshold:
                    is_duplicate = True
                    # Merge information from both publications
                    PublicationDeduplicator.merge_publications(existing_pub, pub)
                    break
            
            if not is_duplicate:
                deduplicated.append(pub)
        
        return deduplicated
    
    @staticmethod
    def merge_publications(primary: Publication, secondary: Publication):
        """Merge information from secondary publication into primary"""
        # Update empty fields in primary with data from secondary
        if not primary.doi and secondary.doi:
            primary.doi = secondary.doi
        if not primary.arxiv_id and secondary.arxiv_id:
            primary.arxiv_id = secondary.arxiv_id
        if not primary.url and secondary.url:
            primary.url = secondary.url
        if not primary.pdf_url and secondary.pdf_url:
            primary.pdf_url = secondary.pdf_url
        if not primary.abstract and secondary.abstract:
            primary.abstract = secondary.abstract
        if not primary.journal and secondary.journal:
            primary.journal = secondary.journal
        if not primary.venue and secondary.venue:
            primary.venue = secondary.venue
        if not primary.bibtex and secondary.bibtex:
            primary.bibtex = secondary.bibtex
            
        # Prefer journal publication over preprint
        if secondary.type == "journal" and primary.type == "preprint":
            primary.type = secondary.type
            primary.journal = secondary.journal
            primary.venue = secondary.venue

def load_config() -> Dict:
    """Load configuration from config file or return defaults"""
    config_path = os.path.join(os.path.dirname(__file__), '..', '_config.yml')
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        return {
            'author_name': config.get('author', {}).get('name', 'Marco Avesani'),
            'orcid_id': config.get('author', {}).get('orcid', '').replace('https://orcid.org/', ''),
            'google_scholar_id': config.get('author', {}).get('googlescholar', '').split('user=')[-1].split('&')[0] if 'user=' in config.get('author', {}).get('googlescholar', '') else '',
            'email': config.get('author', {}).get('email', ''),
        }
    except Exception as e:
        logger.warning(f"Could not load config: {e}")
        return {
            'author_name': 'Marco Avesani',
            'orcid_id': '0000-0001-5122-992X',
            'google_scholar_id': 'g9RL-QcAAAAJ',
            'email': 'marco.avesani@unipd.it',
        }

def save_publications_cache(publications: List[Publication], cache_file: str):
    """Save publications to cache file"""
    try:
        cache_data = {
            'last_updated': datetime.now().isoformat(),
            'publications': [pub.to_dict() for pub in publications]
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Saved {len(publications)} publications to cache")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

def load_publications_cache(cache_file: str) -> List[Publication]:
    """Load publications from cache file"""
    try:
        if not os.path.exists(cache_file):
            return []
            
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            
        publications = []
        for pub_data in cache_data.get('publications', []):
            publications.append(Publication(**pub_data))
            
        logger.info(f"Loaded {len(publications)} publications from cache")
        return publications
        
    except Exception as e:
        logger.error(f"Error loading cache: {e}")
        return []