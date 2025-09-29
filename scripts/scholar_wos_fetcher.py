import logging
from typing import List, Optional
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from publication_utils import Publication, PublicationNormalizer

logger = logging.getLogger(__name__)

# Try to import scholarly, fall back gracefully if not available
try:
    from scholarly import scholarly
    SCHOLARLY_AVAILABLE = True
except ImportError:
    logger.warning("scholarly package not installed. Install with: pip install scholarly")
    SCHOLARLY_AVAILABLE = False

class GoogleScholarFetcher:
    """Fetch publications from Google Scholar using the scholarly package"""
    
    def __init__(self):
        self.normalizer = PublicationNormalizer()
    
    def fetch_publications(self, scholar_id: str = None, author_name: str = None) -> List[Publication]:
        """Fetch publications from Google Scholar"""
        if not SCHOLARLY_AVAILABLE:
            logger.error("scholarly package not available. Please install with: pip install scholarly")
            return []
        
        publications = []
        
        try:
            if scholar_id:
                publications = self._fetch_by_scholar_id(scholar_id)
            elif author_name:
                publications = self._fetch_by_author_name(author_name)
            
            logger.info(f"Found {len(publications)} publications on Google Scholar")
            
        except Exception as e:
            logger.error(f"Error fetching from Google Scholar: {e}")
            
        return publications
    
    def _fetch_by_scholar_id(self, scholar_id: str) -> List[Publication]:
        """Fetch publications by Google Scholar ID"""
        publications = []
        
        try:
            logger.info(f"Fetching Google Scholar profile: {scholar_id}")
            
            # Get author by Scholar ID
            author = scholarly.search_author_id(scholar_id)
            author = scholarly.fill(author, sections=['publications'])
            
            # Process publications in parallel for speed
            pub_list = author.get('publications', [])
            logger.info(f"Processing {len(pub_list)} publications from Google Scholar in parallel...")
            
            publications = self._process_publications_parallel(pub_list, max_workers=100)
                    
        except Exception as e:
            logger.error(f"Error fetching by Google Scholar ID: {e}")
            
        return publications
    
    def _process_publications_parallel(self, pub_list: List, max_workers: int = 5) -> List[Publication]:
        """Process publications in parallel to improve speed"""
        publications = []
        
        def process_single_publication(pub_data):
            """Process a single publication with error handling"""
            try:
                # Fill publication details
                pub_filled = scholarly.fill(pub_data)
                pub = self._parse_scholarly_publication(pub_filled)
                if pub:
                    return pub
            except Exception as e:
                logger.debug(f"Error processing publication: {e}")
            return None
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_pub = {executor.submit(process_single_publication, pub_data): pub_data 
                           for pub_data in pub_list}
            
            # Collect results as they complete
            for future in as_completed(future_to_pub):
                try:
                    result = future.result(timeout=30)  # 30 second timeout per publication
                    if result:
                        publications.append(result)
                except Exception as e:
                    logger.debug(f"Error in parallel processing: {e}")
                    continue
        
        return publications
    
    def _fetch_by_author_name(self, author_name: str) -> List[Publication]:
        """Search Google Scholar by author name"""
        publications = []
        
        try:
            logger.info(f"Searching Google Scholar for: {author_name}")
            
            # Search for authors
            search_query = scholarly.search_author(author_name)
            
            # Get the first matching author
            try:
                author = next(search_query)
                author = scholarly.fill(author, sections=['publications'])
                
                # Process publications in parallel
                pub_list = author.get('publications', [])
                logger.info(f"Processing {len(pub_list)} publications from Google Scholar search in parallel...")
                publications = self._process_publications_parallel(pub_list, max_workers=3)
                        
            except StopIteration:
                logger.warning(f"No author found for: {author_name}")
                
        except Exception as e:
            logger.error(f"Error searching Google Scholar by name: {e}")
            
        return publications
    
    def _parse_scholarly_publication(self, pub_data: dict) -> Optional[Publication]:
        """Parse publication data from scholarly package"""
        try:
            # Extract title
            title = pub_data.get('bib', {}).get('title', '')
            title = self.normalizer.clean_title(title)
            
            if not title:
                return None
            
            # Extract authors
            authors = []
            author_list = pub_data.get('bib', {}).get('author', [])
            if isinstance(author_list, list):
                for author in author_list:
                    if author:
                        authors.append(self.normalizer.normalize_author_name(author))
            elif isinstance(author_list, str):
                # Sometimes authors come as a string
                author_names = [name.strip() for name in author_list.split(' and ')]
                for name in author_names:
                    if name:
                        authors.append(self.normalizer.normalize_author_name(name))
            
            # Extract journal/venue
            journal = pub_data.get('bib', {}).get('venue', '') or pub_data.get('bib', {}).get('journal', '')
            
            # Extract year
            year = 0
            year_str = pub_data.get('bib', {}).get('pub_year', '')
            if year_str:
                try:
                    year = int(year_str)
                except (ValueError, TypeError):
                    year = 0
            
            # Extract URL/DOI
            url = pub_data.get('pub_url', '') or pub_data.get('eprint_url', '')
            
            # Extract abstract
            abstract = pub_data.get('bib', {}).get('abstract', '')
            
            # Extract volume and pages
            volume = pub_data.get('bib', {}).get('volume', '')
            pages = pub_data.get('bib', {}).get('pages', '')
            
            # Determine publication type
            pub_type = self.normalizer.detect_publication_type(journal, journal, "", title, "")
            
            # Try to extract DOI from URL or other fields
            doi = ""
            if url:
                doi_match = re.search(r'10\.\d+/[^\s]+', url)
                if doi_match:
                    doi = doi_match.group()
            
            publication = Publication(
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                url=url,
                doi=doi,
                abstract=abstract,
                volume=volume,
                pages=pages,
                type=pub_type,
                venue=journal
            )
            
            return publication
            
        except Exception as e:
            logger.error(f"Error parsing scholarly publication: {e}")
            return None

class WebOfScienceFetcher:
    """Fetch publications from Web of Science (requires institutional access)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://wos-api.clarivate.com/api/wos"
        self.normalizer = PublicationNormalizer()
    
    def fetch_publications(self, author_name: str) -> List[Publication]:
        """Fetch publications from Web of Science (requires API key)"""
        if not self.api_key:
            logger.warning("Web of Science API key not provided, skipping WoS fetch")
            return []
        
        publications = []
        
        try:
            # Web of Science API implementation would go here
            # This requires a paid subscription and institutional access
            logger.info("Web of Science fetching would require institutional access")
            
        except Exception as e:
            logger.error(f"Error fetching from Web of Science: {e}")
            
        return publications