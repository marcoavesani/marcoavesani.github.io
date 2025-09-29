import requests
import feedparser
import re
import logging
from typing import List, Optional
from datetime import datetime
from publication_utils import Publication, PublicationNormalizer

logger = logging.getLogger(__name__)

class ArxivFetcher:
    """Fetch publications from arXiv"""
    
    def __init__(self):
        self.base_url = "http://export.arxiv.org/api/query"
        self.normalizer = PublicationNormalizer()
    
    def search_by_author(self, author_name: str, max_results: int = 100) -> List[Publication]:
        """Search arXiv for publications by author name"""
        publications = []
        
        try:
            # Clean author name for search
            search_query = f'au:"{author_name}"'
            
            params = {
                'search_query': search_query,
                'start': 0,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            
            logger.info(f"Searching arXiv for author: {author_name}")
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse the Atom feed
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries:
                pub = self._parse_arxiv_entry(entry)
                if pub:
                    publications.append(pub)
                    
            logger.info(f"Found {len(publications)} publications on arXiv")
            
        except Exception as e:
            logger.error(f"Error fetching from arXiv: {e}")
            
        return publications
    
    def _parse_arxiv_entry(self, entry) -> Optional[Publication]:
        """Parse a single arXiv entry"""
        try:
            # Extract arXiv ID
            arxiv_id = entry.id.split('/')[-1]
            if 'v' in arxiv_id:
                arxiv_id = arxiv_id.split('v')[0]  # Remove version number
            
            # Extract authors
            authors = []
            if hasattr(entry, 'authors'):
                for author in entry.authors:
                    name = self.normalizer.normalize_author_name(author.name)
                    authors.append(name)
            
            # Extract title and clean it
            title = self.normalizer.clean_title(entry.title.replace('\n', ' '))
            
            # Extract abstract
            abstract = entry.summary.replace('\n', ' ').strip() if hasattr(entry, 'summary') else ""
            
            # Extract publication date
            published = entry.get('published', '')
            year = self.normalizer.extract_year_from_date(published)
            
            # Build URLs
            arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            
            # Check if this is a preprint or published version
            journal = ""
            pub_type = "preprint"
            
            # Sometimes arXiv entries include journal reference
            if hasattr(entry, 'arxiv_journal_ref'):
                journal = entry.arxiv_journal_ref
                pub_type = "journal"
            
            publication = Publication(
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                arxiv_id=arxiv_id,
                url=arxiv_url,
                pdf_url=pdf_url,
                abstract=abstract,
                type=pub_type,
                venue="arXiv" if not journal else journal
            )
            
            return publication
            
        except Exception as e:
            logger.error(f"Error parsing arXiv entry: {e}")
            return None

class CrossRefFetcher:
    """Fetch publications from CrossRef using DOI"""
    
    def __init__(self):
        self.base_url = "https://api.crossref.org/works"
        self.normalizer = PublicationNormalizer()
    
    def search_by_author(self, author_name: str, max_results: int = 100) -> List[Publication]:
        """Search CrossRef for publications by author"""
        publications = []
        
        try:
            # Clean author name for search
            query = f'author:"{author_name}"'
            
            params = {
                'query': query,
                'rows': min(max_results, 1000),  # CrossRef limit
                'sort': 'published',
                'order': 'desc'
            }
            
            headers = {
                'User-Agent': 'Academic Website Updater (mailto:marco.avesani@unipd.it)'
            }
            
            logger.info(f"Searching CrossRef for author: {author_name}")
            response = requests.get(self.base_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            for item in data.get('message', {}).get('items', []):
                pub = self._parse_crossref_item(item)
                if pub and self._is_relevant_author(pub.authors, author_name):
                    publications.append(pub)
                    
            logger.info(f"Found {len(publications)} publications on CrossRef")
            
        except Exception as e:
            logger.error(f"Error fetching from CrossRef: {e}")
            
        return publications
    
    def _parse_crossref_item(self, item) -> Optional[Publication]:
        """Parse a single CrossRef item"""
        try:
            # Extract title
            title_list = item.get('title', [])
            title = self.normalizer.clean_title(title_list[0]) if title_list else ""
            
            if not title:
                return None
            
            # Extract authors
            authors = []
            for author in item.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                if family:
                    name = f"{given} {family}".strip()
                    authors.append(self.normalizer.normalize_author_name(name))
            
            # Extract journal/venue
            journal = item.get('container-title', [''])[0]
            
            # Extract year
            published_date = item.get('published-print') or item.get('published-online') or item.get('created')
            year = 0
            if published_date and 'date-parts' in published_date:
                date_parts = published_date['date-parts'][0]
                if date_parts:
                    year = date_parts[0]
            
            # Extract other metadata
            volume = item.get('volume', '')
            pages = item.get('page', '')
            doi = item.get('DOI', '')
            
            # Build URL
            url = f"https://doi.org/{doi}" if doi else ""
            
            # Determine publication type
            pub_type = self.normalizer.detect_publication_type(journal, journal, "")
            
            publication = Publication(
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                volume=volume,
                pages=pages,
                doi=doi,
                url=url,
                type=pub_type,
                venue=journal
            )
            
            return publication
            
        except Exception as e:
            logger.error(f"Error parsing CrossRef item: {e}")
            return None
    
    def _is_relevant_author(self, authors: List[str], target_author: str) -> bool:
        """Check if the target author is in the authors list"""
        target_lower = target_author.lower()
        
        for author in authors:
            if target_lower in author.lower():
                return True
                
        return False

class DOIFetcher:
    """Fetch publication details using DOI"""
    
    def __init__(self):
        self.normalizer = PublicationNormalizer()
    
    def fetch_by_doi(self, doi: str) -> Optional[Publication]:
        """Fetch publication details by DOI"""
        try:
            headers = {
                'Accept': 'application/citeproc+json',
                'User-Agent': 'Academic Website Updater (mailto:marco.avesani@unipd.it)'
            }
            
            url = f"https://doi.org/{doi}"
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return self._parse_doi_data(data, doi)
            
        except Exception as e:
            logger.error(f"Error fetching DOI {doi}: {e}")
            return None
    
    def _parse_doi_data(self, data: dict, doi: str) -> Optional[Publication]:
        """Parse DOI response data"""
        try:
            # Extract title
            title = self.normalizer.clean_title(data.get('title', ''))
            if not title:
                return None
            
            # Extract authors
            authors = []
            for author in data.get('author', []):
                given = author.get('given', '')
                family = author.get('family', '')
                if family:
                    name = f"{given} {family}".strip()
                    authors.append(self.normalizer.normalize_author_name(name))
            
            # Extract journal
            journal = data.get('container-title', '')
            
            # Extract year
            year = 0
            if 'published-print' in data:
                date_parts = data['published-print'].get('date-parts', [[]])[0]
                if date_parts:
                    year = date_parts[0]
            elif 'published-online' in data:
                date_parts = data['published-online'].get('date-parts', [[]])[0]
                if date_parts:
                    year = date_parts[0]
            
            # Extract other metadata
            volume = data.get('volume', '')
            pages = data.get('page', '')
            
            publication = Publication(
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                volume=volume,
                pages=pages,
                doi=doi,
                url=f"https://doi.org/{doi}",
                type=self.normalizer.detect_publication_type(journal, journal, ""),
                venue=journal
            )
            
            return publication
            
        except Exception as e:
            logger.error(f"Error parsing DOI data: {e}")
            return None