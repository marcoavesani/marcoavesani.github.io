import requests
import json
import logging
import time
from typing import List, Optional, Dict
from datetime import datetime
from publication_utils import Publication, PublicationNormalizer

logger = logging.getLogger(__name__)

class ORCIDFetcher:
    """Fetch publications from ORCID API"""
    
    def __init__(self):
        self.base_url = "https://pub.orcid.org/v3.0"
        self.normalizer = PublicationNormalizer()
    
    def fetch_publications(self, orcid_id: str) -> List[Publication]:
        """Fetch all publications for an ORCID ID"""
        publications = []
        
        try:
            # Clean ORCID ID
            if orcid_id.startswith('https://orcid.org/'):
                orcid_id = orcid_id.replace('https://orcid.org/', '')
            
            logger.info(f"Fetching publications from ORCID: {orcid_id}")
            
            # First, get the list of works
            works_url = f"{self.base_url}/{orcid_id}/works"
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'Academic Website Updater (mailto:marco.avesani@unipd.it)'
            }
            
            response = requests.get(works_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            works_data = response.json()
            
            # Get details for each work
            for work_group in works_data.get('group', []):
                for work_summary in work_group.get('work-summary', []):
                    put_code = work_summary.get('put-code')
                    if put_code:
                        pub = self._fetch_work_details(orcid_id, put_code)
                        if pub:
                            publications.append(pub)
                        
                        # Rate limiting - ORCID allows 24 requests per second
                        time.sleep(0.05)
            
            logger.info(f"Found {len(publications)} publications on ORCID")
            
        except Exception as e:
            logger.error(f"Error fetching from ORCID: {e}")
            
        return publications
    
    def _fetch_work_details(self, orcid_id: str, put_code: str) -> Optional[Publication]:
        """Fetch detailed information for a specific work"""
        try:
            work_url = f"{self.base_url}/{orcid_id}/work/{put_code}"
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'Academic Website Updater (mailto:marco.avesani@unipd.it)'
            }
            
            response = requests.get(work_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            work_data = response.json()
            return self._parse_orcid_work(work_data)
            
        except Exception as e:
            logger.error(f"Error fetching work details {put_code}: {e}")
            return None
    
    def _parse_orcid_work(self, work_data: dict) -> Optional[Publication]:
        """Parse ORCID work data into Publication object"""
        try:
            # Extract title
            title_info = work_data.get('title', {})
            title = ""
            if title_info:
                title = title_info.get('title', {}).get('value', '')
            
            title = self.normalizer.clean_title(title)
            if not title:
                return None
            
            # Extract authors (contributors)
            authors = []
            contributors = work_data.get('contributors', {}).get('contributor', [])
            for contrib in contributors:
                credit_name = contrib.get('credit-name')
                if credit_name:
                    name = credit_name.get('value', '')
                    if name:
                        authors.append(self.normalizer.normalize_author_name(name))
            
            # Extract journal
            journal_title = work_data.get('journal-title')
            journal = journal_title.get('value', '') if journal_title else ''
            
            # Extract year
            year = 0
            pub_date = work_data.get('publication-date')
            if pub_date:
                year_info = pub_date.get('year')
                if year_info:
                    year = int(year_info.get('value', 0))
            
            # Extract external IDs (DOI, arXiv, etc.)
            doi = ""
            arxiv_id = ""
            url = ""
            
            external_ids = work_data.get('external-ids', {}).get('external-id', [])
            for ext_id in external_ids:
                id_type = ext_id.get('external-id-type', '').lower()
                id_value = ext_id.get('external-id-value', '')
                id_url = ext_id.get('external-id-url', {}).get('value', '')
                
                if id_type == 'doi':
                    doi = id_value
                    if not url and id_url:
                        url = id_url
                elif id_type == 'arxiv':
                    arxiv_id = id_value
                elif id_type == 'uri' and not url:
                    url = id_value
            
            # Extract work type
            work_type = work_data.get('type', '').lower()
            pub_type = self._map_orcid_type_to_publication_type(work_type)
            
            publication = Publication(
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
            
            return publication
            
        except Exception as e:
            logger.error(f"Error parsing ORCID work: {e}")
            return None
    
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
                type=self.normalizer.detect_publication_type(journal, journal, ""),
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