import requests
import logging
import time
from typing import List, Optional, Dict
from datetime import datetime
import orcid
from publication_utils import Publication, PublicationNormalizer

logger = logging.getLogger(__name__)

class ORCIDFetcher:
    """Fetch publications from ORCID API using official python-orcid package"""
    
    def __init__(self):
        # Initialize ORCID API with client credentials
        self.client_id = "APP-H8TAV228IV5K7XHZ"
        self.client_secret = "bccfe2fb-6b46-49dd-94d8-881c87c09797"
        self.api = orcid.PublicAPI(self.client_id, self.client_secret, sandbox=False)
        self.normalizer = PublicationNormalizer()
    
    def fetch_publications(self, orcid_id: str) -> List[Publication]:
        """Fetch all publications for an ORCID ID using the official orcid package"""
        publications = []
        
        try:
            # Clean ORCID ID
            if orcid_id.startswith('https://orcid.org/'):
                orcid_id = orcid_id.replace('https://orcid.org/', '')
            
            logger.info(f"Fetching publications from ORCID: {orcid_id}")
            
            # Get search token for public access (no user authentication needed)
            search_token = self.api.get_search_token_from_orcid()
            logger.debug(f"Got search token: {search_token[:20]}..." if search_token else "No token")
            
            # Get works summary using the official API
            works_summary = self.api.read_record_public(orcid_id, 'works', search_token)
            
            if not works_summary or 'group' not in works_summary:
                logger.warning(f"No works found for ORCID ID: {orcid_id}")
                return publications
            
            # Extract all put-codes from the works summary
            put_codes = []
            for work_group in works_summary.get('group', []):
                for work_summary in work_group.get('work-summary', []):
                    put_code = work_summary.get('put-code')
                    if put_code:
                        put_codes.append(str(put_code))
            
            logger.info(f"Found {len(put_codes)} works in ORCID profile")
            
            # Fetch multiple works at once (more efficient)
            if put_codes:
                works_details = self.api.read_record_public(orcid_id, 'works', search_token, put_codes)
                
                if works_details and 'bulk' in works_details:
                    for work_item in works_details['bulk']:
                        if work_item and 'work' in work_item:
                            pub = self._parse_orcid_work(work_item['work'])
                            if pub and self._is_quality_publication(pub):
                                publications.append(pub)
                else:
                    logger.warning("No bulk works data returned")
            
            logger.info(f"Found {len(publications)} quality publications on ORCID")
            
        except Exception as e:
            logger.error(f"Error fetching from ORCID: {e}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            
        return publications
    

    
    def _is_quality_publication(self, pub: Publication) -> bool:
        """Check if publication meets quality standards"""
        # Must have title
        if not pub.title:
            return False
        
        # Skip publications with suspicious DOI patterns (likely incomplete records)
        if pub.doi and "/" not in pub.doi and pub.doi.isdigit():
            logger.debug(f"Skipping ORCID work with suspicious DOI: '{pub.title}' - DOI: {pub.doi}")
            return False
            
        # Skip DOIs containing "11577" - these are conference papers
        if pub.doi and "11577" in pub.doi:
            logger.debug(f"Skipping conference paper with 11577 DOI: '{pub.title}' - DOI: {pub.doi}")
            return False
        
        # Skip if no venue/journal and no authors (likely incomplete)
        if not pub.authors and not pub.journal and not pub.venue:
            logger.debug(f"Skipping incomplete ORCID work: '{pub.title}' - no authors, journal, or venue")
            return False
        
        # Prefer publications with authors, but allow those with strong identifiers
        if pub.authors:
            return True
        
        # If no authors, only keep if it has proper DOI or arXiv ID for deduplication
        if (pub.doi and "/" in pub.doi) or pub.arxiv_id:
            logger.debug(f"Keeping ORCID work without authors but with identifier: '{pub.title}'")
            return True
        
        logger.debug(f"Skipping low-quality ORCID work: '{pub.title}' - no authors or strong identifiers")
        return False
    
    def _parse_orcid_work(self, work_data: dict) -> Optional[Publication]:
        """Parse ORCID work data into Publication object"""
        try:
            # Extract basic information
            title = self._extract_title(work_data)
            if not title:
                return None
            
            authors = self._extract_authors(work_data)
            journal = self._extract_journal(work_data)
            year = self._extract_year(work_data)
            doi, arxiv_id, url = self._extract_external_ids(work_data)
            
            # Extract work type - use ORCID type first, then fallback to detection
            work_type = work_data.get('type', '').lower()
            pub_type = self._map_orcid_type_to_publication_type(work_type)
            
            # If ORCID type mapping resulted in default 'journal', use enhanced detection
            if pub_type == 'journal' and not work_type:
                pub_type = self.normalizer.detect_publication_type(journal, journal, arxiv_id, title, doi)
            
            return Publication(
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                doi=doi,
                arxiv_id=arxiv_id,
                url=url,
                type=pub_type,
                venue=journal
            )
            
        except Exception as e:
            logger.error(f"Error parsing ORCID work: {e}")
            return None
    
    def _extract_title(self, work_data: dict) -> str:
        """Extract title from ORCID work data"""
        title_info = work_data.get('title')
        if title_info and isinstance(title_info, dict):
            title_data = title_info.get('title')
            if title_data and isinstance(title_data, dict):
                title = title_data.get('value', '')
                return self.normalizer.clean_title(title)
        return ""
    
    def _extract_authors(self, work_data: dict) -> List[str]:
        """Extract authors from ORCID work data"""
        authors = []
        contributors_data = work_data.get('contributors', {})
        contributors = contributors_data.get('contributor', []) if isinstance(contributors_data, dict) else []
        
        for contrib in contributors:
            name = self._extract_contributor_name(contrib)
            if name:
                authors.append(self.normalizer.normalize_author_name(name))
        
        return authors
    
    def _extract_contributor_name(self, contrib: dict) -> str:
        """Extract name from a single contributor"""
        if not contrib or not isinstance(contrib, dict):
            return ""
        
        credit_name = contrib.get('credit-name', {})
        if isinstance(credit_name, dict):
            return credit_name.get('value', '')
        
        return ""
    
    def _extract_journal(self, work_data: dict) -> str:
        """Extract journal from ORCID work data"""
        journal_title = work_data.get('journal-title')
        if journal_title and isinstance(journal_title, dict):
            return journal_title.get('value', '')
        return ""
    
    def _extract_year(self, work_data: dict) -> int:
        """Extract year from ORCID work data"""
        pub_date = work_data.get('publication-date')
        if pub_date and isinstance(pub_date, dict):
            year_info = pub_date.get('year')
            if year_info and isinstance(year_info, dict):
                try:
                    return int(year_info.get('value', 0))
                except (ValueError, TypeError):
                    pass
        return 0
    
    def _extract_external_ids(self, work_data: dict) -> tuple:
        """Extract external IDs (DOI, arXiv, URL) from ORCID work data"""
        doi = ""
        arxiv_id = ""
        url = ""
        
        external_ids_data = work_data.get('external-ids', {})
        external_ids = external_ids_data.get('external-id', []) if isinstance(external_ids_data, dict) else []
        
        for ext_id in external_ids:
            if not ext_id or not isinstance(ext_id, dict):
                continue
                
            id_type = ext_id.get('external-id-type', '').lower()
            id_value = ext_id.get('external-id-value', '')
            id_url = self._extract_external_id_url(ext_id)
            
            if id_type == 'doi':
                doi = id_value
                if not url and id_url:
                    url = id_url
            elif id_type == 'arxiv':
                arxiv_id = id_value
            elif id_type == 'uri' and not url:
                url = id_value
        
        return doi, arxiv_id, url
    
    def _extract_external_id_url(self, ext_id: dict) -> str:
        """Extract URL from external ID"""
        id_url_data = ext_id.get('external-id-url', {})
        if isinstance(id_url_data, dict):
            return id_url_data.get('value', '')
        return ""
    
    def _map_orcid_type_to_publication_type(self, orcid_type: str) -> str:
        """Map ORCID work type to our publication type"""
        type_mapping = {
            'journal-article': 'journal',
            'conference-paper': 'conference',
            'book': 'book',
            'book-chapter': 'book',
            'preprint': 'preprint',
            'working-paper': 'preprint',
            'report': 'report',
            'thesis': 'thesis',
            'dissertation': 'thesis'
        }
        
        return type_mapping.get(orcid_type, 'journal')

class ScopusFetcher:
    """Fetch publications from Scopus API (requires API key)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.elsevier.com/content"
        self.normalizer = PublicationNormalizer()
    
    def fetch_publications(self, author_id: str = None, author_name: str = None) -> List[Publication]:
        """Fetch publications from Scopus (requires API key)"""
        if not self.api_key:
            logger.warning("Scopus API key not provided, skipping Scopus fetch")
            return []
        
        publications = []
        
        try:
            if author_id:
                publications = self._fetch_by_author_id(author_id)
            elif author_name:
                publications = self._fetch_by_author_name(author_name)
            
            logger.info(f"Found {len(publications)} publications on Scopus")
            
        except Exception as e:
            logger.error(f"Error fetching from Scopus: {e}")
            
        return publications
    
    def _fetch_by_author_id(self, author_id: str) -> List[Publication]:
        """Fetch publications by Scopus author ID"""
        publications = []
        
        try:
            url = f"{self.base_url}/search/scopus"
            params = {
                'query': f'AU-ID({author_id})',
                'apiKey': self.api_key,
                'count': 100,
                'sort': 'pubyear',
                'view': 'COMPLETE'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            for entry in data.get('search-results', {}).get('entry', []):
                pub = self._parse_scopus_entry(entry)
                if pub:
                    publications.append(pub)
                    
        except Exception as e:
            logger.error(f"Error fetching by Scopus author ID: {e}")
            
        return publications
    
    def _fetch_by_author_name(self, author_name: str) -> List[Publication]:
        """Fetch publications by author name"""
        publications = []
        
        try:
            url = f"{self.base_url}/search/scopus"
            params = {
                'query': f'AUTHOR-NAME("{author_name}")',
                'apiKey': self.api_key,
                'count': 100,
                'sort': 'pubyear',
                'view': 'COMPLETE'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            for entry in data.get('search-results', {}).get('entry', []):
                pub = self._parse_scopus_entry(entry)
                if pub and self._is_relevant_author(pub.authors, author_name):
                    publications.append(pub)
                    
        except Exception as e:
            logger.error(f"Error fetching by Scopus author name: {e}")
            
        return publications
    
    def _parse_scopus_entry(self, entry: dict) -> Optional[Publication]:
        """Parse Scopus entry into Publication object"""
        try:
            # Extract title
            title = self.normalizer.clean_title(entry.get('dc:title', ''))
            if not title:
                return None
            
            # Extract authors
            authors = []
            author_info = entry.get('author', [])
            if isinstance(author_info, list):
                for author in author_info:
                    name = author.get('authname', '')
                    if name:
                        authors.append(self.normalizer.normalize_author_name(name))
            
            # Extract journal
            journal = entry.get('prism:publicationName', '')
            
            # Extract year
            year = 0
            cover_date = entry.get('prism:coverDate', '')
            if cover_date:
                year = self.normalizer.extract_year_from_date(cover_date)
            
            # Extract other metadata
            volume = entry.get('prism:volume', '')
            pages = entry.get('prism:pageRange', '')
            doi = entry.get('prism:doi', '')
            
            # Build URL
            url = f"https://doi.org/{doi}" if doi else entry.get('link', [{}])[0].get('@href', '')
            
            publication = Publication(
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                volume=volume,
                pages=pages,
                doi=doi,
                url=url,
                type=self.normalizer.detect_publication_type(journal, journal, "", title, doi),
                venue=journal
            )
            
            return publication
            
        except Exception as e:
            logger.error(f"Error parsing Scopus entry: {e}")
            return None
    
    def _is_relevant_author(self, authors: List[str], target_author: str) -> bool:
        """Check if the target author is in the authors list"""
        target_lower = target_author.lower()
        
        for author in authors:
            if target_lower in author.lower():
                return True
                
        return False