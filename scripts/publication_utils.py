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
        # Determine the primary paper URL (prioritize DOI for journals, arXiv for preprints)
        paper_url = ""
        if self.doi:
            paper_url = f"https://doi.org/{self.doi}"
        elif self.arxiv_id:
            paper_url = f"https://arxiv.org/abs/{self.arxiv_id}"
        elif self.url:
            paper_url = self.url
            
        content = f"""---
title: "{self.title}"
collection: publications
permalink: /publication/{self.get_citation_key()}
excerpt: '{self.abstract[:200]}...' if len(self.abstract) > 200 else self.abstract
date: {self.year}-01-01
venue: '{self.venue or self.journal}'
paperurl: '{paper_url}'
citation: '{self.format_citation()}'
---

{self.abstract}

**Authors:** {self.format_authors(highlight_author)}

"""
        
        # Add links - always show both journal and arXiv for journal papers
        links = []
        
        # For journal papers, show journal link first, then arXiv
        if self.type.lower() == 'journal':
            if self.doi:
                journal_url = f"https://doi.org/{self.doi}"
                links.append(f"[Journal]({journal_url}){{: .btn .btn--info}}")
            elif self.url and (not self.arxiv_id or self.url != f"https://arxiv.org/abs/{self.arxiv_id}"):
                links.append(f"[Journal]({self.url}){{: .btn .btn--info}}")
                
            if self.arxiv_id:
                arxiv_url = f"https://arxiv.org/abs/{self.arxiv_id}"
                links.append(f"[ArXiv]({arxiv_url}){{: .btn .btn--info}}")
        else:
            # For preprints, show arXiv first, then other URLs
            if self.arxiv_id:
                arxiv_url = f"https://arxiv.org/abs/{self.arxiv_id}"
                links.append(f"[ArXiv]({arxiv_url}){{: .btn .btn--info}}")
            elif self.url:
                links.append(f"[Paper]({self.url}){{: .btn .btn--info}}")
                
        # Add PDF link if different from arXiv PDF
        if self.pdf_url and (not self.arxiv_id or self.pdf_url != f"https://arxiv.org/pdf/{self.arxiv_id}.pdf"):
            links.append(f"[PDF]({self.pdf_url}){{: .btn .btn--info}}")
            
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
    def detect_publication_type(venue: str, journal: str, arxiv_id: str, title: str = "", doi: str = "") -> str:
        """Detect publication type based on venue/journal information and other clues"""
        venue_lower = (venue or "").lower()
        journal_lower = (journal or "").lower()
        title_lower = (title or "").lower()
        
        # Conference indicators in title or venue
        conference_indicators = [
            "conference", "proceedings", "workshop", "symposium", "congress",
            "meeting", "session", "presentation", "talk", "poster"
        ]
        
        # Journal indicators
        journal_indicators = [
            "journal", "letters", "review", "transactions", "magazine",
            "communications", "reports", "advances", "nature", "science",
            "physical review", "ieee", "optics", "quantum"
        ]
        
        if arxiv_id and not journal:
            return "preprint"
        elif any(word in venue_lower or word in journal_lower or word in title_lower
                for word in conference_indicators):
            return "conference"
        elif any(word in venue_lower or word in journal_lower 
                for word in journal_indicators):
            return "journal"
        elif any(word in venue_lower or word in journal_lower 
                for word in ["book", "chapter"]):
            return "book"
        elif doi and "11577" in doi:
            # DOIs containing "11577" are conference papers
            return "conference"
        elif not venue and not journal and doi and "/" not in doi:
            # Suspicious DOI format often indicates conference or incomplete record
            return "conference"
        else:
            return "journal"  # default

class PublicationDeduplicator:
    """Remove duplicate publications based on various criteria"""
    
    @staticmethod
    def compute_similarity_score(pub1: Publication, pub2: Publication) -> float:
        """Compute similarity score between two publications"""
        score = 0.0
        
        # DOI/ArXiv ID exact match (highest priority)
        if pub1.doi and pub2.doi and pub1.doi.lower().strip() == pub2.doi.lower().strip():
            return 1.0  # Perfect match
        if pub1.arxiv_id and pub2.arxiv_id and pub1.arxiv_id.lower().strip() == pub2.arxiv_id.lower().strip():
            return 1.0  # Perfect match
        
        # URL similarity for same DOI with different formats
        if pub1.url and pub2.url:
            # Extract DOI from URLs if present
            doi_pattern = r'10\.\d+/[^\s]+'
            doi1_match = re.search(doi_pattern, pub1.url)
            doi2_match = re.search(doi_pattern, pub2.url) 
            if doi1_match and doi2_match and doi1_match.group() == doi2_match.group():
                return 1.0  # Same DOI in URLs
        
        # Normalize titles for comparison
        title1 = re.sub(r'[^\w\s]', '', pub1.title.lower().strip())
        title2 = re.sub(r'[^\w\s]', '', pub2.title.lower().strip())
        title1 = re.sub(r'\s+', ' ', title1)
        title2 = re.sub(r'\s+', ' ', title2)
        
        # Title similarity (very important)
        if title1 == title2:
            score += 0.4
        elif title1 in title2 or title2 in title1:
            score += 0.35
        else:
            # Word overlap for titles - be more aggressive
            words1 = set(title1.split())
            words2 = set(title2.split())
            if words1 and words2 and len(words1) > 2 and len(words2) > 2:
                overlap = len(words1.intersection(words2)) / len(words1.union(words2))
                # Check for key phrase matches that indicate same paper
                key_phrases1 = [' '.join(words1)[i:i+20] for i in range(0, len(' '.join(words1)), 5)]
                key_phrases2 = [' '.join(words2)[i:i+20] for i in range(0, len(' '.join(words2)), 5)]
                
                # If significant word overlap or key phrases match
                if overlap > 0.6:  # Lower threshold for word overlap
                    score += overlap * 0.35
                elif any(phrase in ' '.join(words2) for phrase in key_phrases1 if len(phrase) > 15):
                    score += 0.3  # Partial phrase match
        
        # Author similarity (very important for academic papers)
        authors1 = {author.lower().strip().replace('.', '') for author in pub1.authors if author.strip()}
        authors2 = {author.lower().strip().replace('.', '') for author in pub2.authors if author.strip()}
        
        # Special handling for missing authors cases
        if not authors1 or not authors2:
            # If titles are identical or very similar, boost score significantly
            if title1 == title2:
                score += 0.6  # Very high boost for identical titles
            elif len(title1) > 10 and len(title2) > 10:
                # Check if titles are very similar (substring match)
                if title1 in title2 or title2 in title1:
                    score += 0.5
                # Or if most words match
                words1_set = set(title1.split())
                words2_set = set(title2.split())
                if len(words1_set.intersection(words2_set)) / len(words1_set.union(words2_set)) > 0.8:
                    score += 0.5
            
            # Additional boost if years match
            if pub1.year == pub2.year and pub1.year > 0:
                score += 0.2
        elif authors1 and authors2:
            # Check for exact author matches
            common_authors = 0
            for auth1 in authors1:
                for auth2 in authors2:
                    # Check if last names match (common in academic citations)
                    last1 = auth1.split()[-1] if auth1.split() else ''
                    last2 = auth2.split()[-1] if auth2.split() else ''
                    if last1 and last2 and len(last1) > 2 and last1 == last2:
                        common_authors += 1
                        break
            
            if len(authors1) > 0 and len(authors2) > 0:
                author_similarity = common_authors / max(len(authors1), len(authors2))
                score += author_similarity * 0.4
        
        # Year similarity (less important but still relevant)
        if pub1.year == pub2.year and pub1.year > 0:
            score += 0.1
        elif pub1.year > 0 and pub2.year > 0 and abs(pub1.year - pub2.year) <= 1:
            score += 0.05  # Allow for slight year differences
        
        # URL similarity (can help identify duplicates)
        if pub1.url and pub2.url:
            url1_clean = pub1.url.lower().replace('http://', '').replace('https://', '').replace('www.', '')
            url2_clean = pub2.url.lower().replace('http://', '').replace('https://', '').replace('www.', '')
            if url1_clean == url2_clean:
                score += 0.1
            
        return score
    
    @staticmethod
    def deduplicate_publications(publications: List[Publication], 
                               threshold: float = 0.5) -> List[Publication]:
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
        """Merge information from secondary publication into primary, prioritizing journal info."""
        
        # Determine which publication has more complete information
        primary_completeness = len([f for f in [primary.title, primary.journal, primary.doi, primary.arxiv_id] if f]) + len(primary.authors)
        secondary_completeness = len([f for f in [secondary.title, secondary.journal, secondary.doi, secondary.arxiv_id] if f]) + len(secondary.authors)
        
        # Choose the more complete publication as the base
        if secondary_completeness > primary_completeness:
            primary, secondary = secondary, primary
        
        # Determine publication types
        is_primary_journal = primary.type == 'journal'
        is_secondary_journal = secondary.type == 'journal'
        is_primary_preprint = primary.type == 'preprint'
        is_secondary_preprint = secondary.type == 'preprint'

        # If one is a journal and the other is a preprint, prioritize the journal's metadata
        if (is_primary_journal and is_secondary_preprint) or (is_secondary_journal and is_primary_preprint):
            journal_pub = primary if is_primary_journal else secondary
            preprint_pub = secondary if is_primary_journal else primary
            
            # Use journal metadata as base
            primary.title = journal_pub.title if journal_pub.title else preprint_pub.title
            primary.authors = journal_pub.authors if journal_pub.authors else preprint_pub.authors
            primary.journal = journal_pub.journal
            primary.year = journal_pub.year if journal_pub.year > 0 else preprint_pub.year
            primary.volume = journal_pub.volume
            primary.pages = journal_pub.pages
            primary.doi = journal_pub.doi
            primary.type = 'journal'
            primary.venue = journal_pub.journal
            
            # Preserve arXiv ID from either source
            primary.arxiv_id = journal_pub.arxiv_id or preprint_pub.arxiv_id
            
            # Choose the best URL (prefer DOI)
            if primary.doi:
                primary.url = f"https://doi.org/{primary.doi}"
            elif journal_pub.url:
                primary.url = journal_pub.url
            else:
                primary.url = preprint_pub.url
        else:
            # Standard merge logic - fill in missing information
            if not primary.doi and secondary.doi: 
                primary.doi = secondary.doi
            if not primary.arxiv_id and secondary.arxiv_id: 
                primary.arxiv_id = secondary.arxiv_id
            if not primary.url and secondary.url: 
                primary.url = secondary.url
            if not primary.journal and secondary.journal: 
                primary.journal = secondary.journal
            if not primary.venue and secondary.venue: 
                primary.venue = secondary.venue
            if not primary.authors: 
                primary.authors = secondary.authors
            if not primary.title and secondary.title: 
                primary.title = secondary.title
            
            # Prefer journal type over preprint
            if is_secondary_journal and not is_primary_journal:
                primary.type = "journal"
                if secondary.journal: primary.journal = secondary.journal
                if secondary.venue: primary.venue = secondary.venue

        # Always merge additional metadata
        if not primary.pdf_url and secondary.pdf_url: primary.pdf_url = secondary.pdf_url
        if not primary.abstract and secondary.abstract: primary.abstract = secondary.abstract
        if not primary.bibtex and secondary.bibtex: primary.bibtex = secondary.bibtex
        if not primary.volume and secondary.volume: primary.volume = secondary.volume
        if not primary.pages and secondary.pages: primary.pages = secondary.pages

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