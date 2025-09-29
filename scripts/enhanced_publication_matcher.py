import requests
import re
import logging
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from publication_utils import Publication, PublicationNormalizer

logger = logging.getLogger(__name__)

class EnhancedPublicationMatcher:
    """
    Enhanced publication fetcher that uses arXiv as primary source and enriches
    with journal information from ORCID and Scholar
    """
    
    def __init__(self):
        self.normalizer = PublicationNormalizer()
        
    def enrich_arxiv_publications(self, arxiv_pubs: List[Publication], 
                                orcid_pubs: List[Publication], 
                                scholar_pubs: List[Publication] = None) -> List[Publication]:
        """
        Enrich arXiv publications with journal information from other sources
        
        Strategy:
        1. For each arXiv paper, look for journal reference in arXiv metadata
        2. If no journal info, search ORCID/Scholar for matching titles
        3. Extract DOI and journal info from matches
        4. Create complete publication records
        """
        enhanced_publications = []
        all_other_pubs = orcid_pubs + (scholar_pubs or [])
        
        logger.info(f"Enriching {len(arxiv_pubs)} arXiv publications with journal data from {len(all_other_pubs)} other sources")
        
        for arxiv_pub in arxiv_pubs:
            enhanced_pub = self._enrich_single_publication(arxiv_pub, all_other_pubs)
            enhanced_publications.append(enhanced_pub)
            
        return enhanced_publications
    
    def _enrich_single_publication(self, arxiv_pub: Publication, other_pubs: List[Publication]) -> Publication:
        """Enrich a single arXiv publication with journal information"""
        
        # Start with the arXiv publication
        enhanced_pub = Publication(
            title=arxiv_pub.title,
            authors=arxiv_pub.authors,
            journal=arxiv_pub.journal,
            year=arxiv_pub.year,
            volume=arxiv_pub.volume,
            pages=arxiv_pub.pages,
            doi=arxiv_pub.doi,
            arxiv_id=arxiv_pub.arxiv_id,
            url=arxiv_pub.url,
            pdf_url=arxiv_pub.pdf_url,
            abstract=arxiv_pub.abstract,
            type=arxiv_pub.type,
            venue=arxiv_pub.venue
        )
        
        # Step 1: Extract journal info from arXiv metadata if available
        journal_info = self._extract_arxiv_journal_info(arxiv_pub)
        if journal_info:
            enhanced_pub.journal = journal_info.get('journal', enhanced_pub.journal)
            enhanced_pub.volume = journal_info.get('volume', enhanced_pub.volume)
            enhanced_pub.pages = journal_info.get('pages', enhanced_pub.pages)
            enhanced_pub.doi = journal_info.get('doi', enhanced_pub.doi)
            enhanced_pub.type = "journal"
            enhanced_pub.venue = enhanced_pub.journal
            
        # Step 2: If no journal info yet, search for matches in other sources
        if not enhanced_pub.journal or enhanced_pub.type == "preprint":
            match = self._find_matching_publication(arxiv_pub, other_pubs)
            if match:
                logger.info(f"Found journal match for arXiv paper: '{arxiv_pub.title[:50]}...'")
                enhanced_pub = self._merge_publication_data(enhanced_pub, match)
        
        return enhanced_pub
    
    def _extract_arxiv_journal_info(self, arxiv_pub: Publication) -> Optional[Dict]:
        """Extract journal information from arXiv metadata"""
        
        # Try to get additional metadata from arXiv API
        if not arxiv_pub.arxiv_id:
            return None
            
        try:
            # Query arXiv API for full metadata
            api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_pub.arxiv_id}"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            import feedparser
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                return None
                
            entry = feed.entries[0]
            journal_info = {}
            
            # Check for journal reference
            if hasattr(entry, 'arxiv_journal_ref'):
                journal_ref = entry.arxiv_journal_ref
                parsed_ref = self._parse_journal_reference(journal_ref)
                journal_info.update(parsed_ref)
                
            # Check for DOI in the entry
            if hasattr(entry, 'arxiv_doi'):
                journal_info['doi'] = entry.arxiv_doi
                
            # Look for DOI in comments or links
            if hasattr(entry, 'arxiv_comment'):
                comment = entry.arxiv_comment
                doi_match = re.search(r'doi:?\s*([0-9]+\.[0-9]+/[^\s]+)', comment, re.IGNORECASE)
                if doi_match:
                    journal_info['doi'] = doi_match.group(1)
                    
            # Look for journal info in tags
            if hasattr(entry, 'tags'):
                for tag in entry.tags:
                    if 'journal' in tag.get('term', '').lower():
                        # Extract journal info from tag
                        pass
                        
            return journal_info if journal_info else None
            
        except Exception as e:
            logger.debug(f"Could not extract additional arXiv metadata: {e}")
            return None
    
    def _parse_journal_reference(self, journal_ref: str) -> Dict:
        """Parse journal reference string to extract structured information"""
        journal_info = {}
        
        # Common patterns for journal references
        patterns = [
            # Pattern: "Journal Name Vol (Year) Pages"
            r'^(.+?)\s+(\d+)\s*\((\d{4})\)\s*(.+)$',
            # Pattern: "Journal Name, Vol, Pages (Year)"
            r'^(.+?),\s*(\d+),\s*(.+?)\s*\((\d{4})\)$',
            # Pattern: "Journal Name Vol, Pages (Year)"
            r'^(.+?)\s+(\d+),\s*(.+?)\s*\((\d{4})\)$',
            # Pattern: "Journal Name (Year)"
            r'^(.+?)\s*\((\d{4})\)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, journal_ref.strip())
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    journal_info['journal'] = groups[0].strip()
                    if len(groups) >= 3 and groups[1].isdigit():
                        journal_info['volume'] = groups[1]
                    if len(groups) >= 4:
                        # Extract year and pages
                        for group in groups[1:]:
                            if group.isdigit() and len(group) == 4:
                                journal_info['year'] = int(group)
                            elif '-' in group or group.isdigit():
                                journal_info['pages'] = group
                break
        
        # If no pattern matched, just use the whole string as journal name
        if not journal_info and journal_ref:
            journal_info['journal'] = journal_ref.strip()
            
        return journal_info
    
    def _find_matching_publication(self, arxiv_pub: Publication, other_pubs: List[Publication]) -> Optional[Publication]:
        """Find a matching publication in other sources based on title similarity"""
        
        best_match = None
        best_score = 0.8  # Minimum similarity threshold
        
        arxiv_title = self.normalizer.clean_title(arxiv_pub.title)
        
        for other_pub in other_pubs:
            other_title = self.normalizer.clean_title(other_pub.title)
            
            # Calculate similarity
            similarity = SequenceMatcher(None, arxiv_title, other_title).ratio()
            
            if similarity > best_score:
                # Additional checks to confirm it's the same paper
                if self._additional_match_checks(arxiv_pub, other_pub):
                    best_match = other_pub
                    best_score = similarity
                    
        if best_match:
            logger.debug(f"Found match with similarity {best_score:.3f}: '{best_match.title[:50]}...'")
            
        return best_match
    
    def _additional_match_checks(self, arxiv_pub: Publication, other_pub: Publication) -> bool:
        """Additional checks to confirm publications are the same"""
        
        # Check if years are close (within 2 years - arXiv usually comes first)
        if arxiv_pub.year and other_pub.year:
            year_diff = abs(arxiv_pub.year - other_pub.year)
            if year_diff > 2:
                return False
                
        # Check if there's author overlap
        if arxiv_pub.authors and other_pub.authors:
            arxiv_authors = {self.normalizer.normalize_author_name(a).lower() for a in arxiv_pub.authors}
            other_authors = {self.normalizer.normalize_author_name(a).lower() for a in other_pub.authors}
            
            # Check for substantial author overlap
            if arxiv_authors and other_authors:
                overlap = len(arxiv_authors.intersection(other_authors))
                overlap_ratio = overlap / min(len(arxiv_authors), len(other_authors))
                if overlap_ratio < 0.5:  # At least 50% author overlap
                    return False
                    
        # If DOI is available in other publication, it's likely the journal version
        if other_pub.doi and not arxiv_pub.doi:
            return True
            
        # If other publication has journal info and arXiv doesn't
        if other_pub.journal and not arxiv_pub.journal:
            return True
            
        return True
    
    def _merge_publication_data(self, arxiv_pub: Publication, journal_pub: Publication) -> Publication:
        """Merge arXiv publication with journal publication data"""
        
        # Start with arXiv data and enhance with journal data
        merged = Publication(
            title=arxiv_pub.title,  # Keep arXiv title (often cleaner)
            authors=journal_pub.authors or arxiv_pub.authors,  # Prefer journal authors (more complete)
            journal=journal_pub.journal,  # Use journal information
            year=journal_pub.year or arxiv_pub.year,  # Prefer journal year
            volume=journal_pub.volume,
            pages=journal_pub.pages,
            doi=journal_pub.doi,
            arxiv_id=arxiv_pub.arxiv_id,  # Keep arXiv ID
            url=journal_pub.url or arxiv_pub.url,  # Prefer journal URL
            pdf_url=arxiv_pub.pdf_url,  # Keep arXiv PDF
            abstract=arxiv_pub.abstract or journal_pub.abstract,  # Prefer arXiv abstract
            type="journal",  # It's now a journal publication
            venue=journal_pub.journal or journal_pub.venue
        )
        
        return merged
    
    def get_publication_statistics(self, publications: List[Publication]) -> Dict:
        """Get statistics about the enriched publications"""
        stats = {
            'total': len(publications),
            'with_arxiv': len([p for p in publications if p.arxiv_id]),
            'with_journal': len([p for p in publications if p.journal]),
            'with_doi': len([p for p in publications if p.doi]),
            'journal_papers': len([p for p in publications if p.type == 'journal']),
            'preprints': len([p for p in publications if p.type == 'preprint']),
        }
        
        return stats