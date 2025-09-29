import os
import logging
from typing import List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import re
from publication_utils import Publication, PublicationNormalizer

logger = logging.getLogger(__name__)

class GoogleScholarFetcher:
    """Fetch publications from Google Scholar"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.normalizer = PublicationNormalizer()
        self.driver = None
    
    def __enter__(self):
        self._setup_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
    
    def _setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
        except Exception as e:
            logger.error(f"Error setting up Chrome driver: {e}")
            raise
    
    def fetch_publications(self, scholar_id: str = None, author_name: str = None) -> List[Publication]:
        """Fetch publications from Google Scholar"""
        if not self.driver:
            self._setup_driver()
        
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
            # Build URL for the author's profile
            url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
            
            logger.info(f"Fetching Google Scholar profile: {scholar_id}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(2)
            
            # Handle "Show more" button to load all publications
            self._load_all_publications()
            
            # Find all publication rows
            pub_elements = self.driver.find_elements(By.CSS_SELECTOR, "tr.gsc_a_tr")
            
            for pub_element in pub_elements:
                pub = self._parse_scholar_publication_row(pub_element)
                if pub:
                    publications.append(pub)
                    
        except Exception as e:
            logger.error(f"Error fetching by Google Scholar ID: {e}")
            
        return publications
    
    def _fetch_by_author_name(self, author_name: str) -> List[Publication]:
        """Search Google Scholar by author name"""
        publications = []
        
        try:
            # Search for the author
            search_url = f"https://scholar.google.com/citations?hl=en&view_op=search_authors&mauthors={author_name}"
            
            logger.info(f"Searching Google Scholar for: {author_name}")
            self.driver.get(search_url)
            
            time.sleep(2)
            
            # Find the first author profile link
            author_links = self.driver.find_elements(By.CSS_SELECTOR, "h3.gs_ai_name a")
            
            if author_links:
                # Click on the first author profile
                author_links[0].click()
                time.sleep(2)
                
                # Load all publications
                self._load_all_publications()
                
                # Find all publication rows
                pub_elements = self.driver.find_elements(By.CSS_SELECTOR, "tr.gsc_a_tr")
                
                for pub_element in pub_elements:
                    pub = self._parse_scholar_publication_row(pub_element)
                    if pub:
                        publications.append(pub)
                        
        except Exception as e:
            logger.error(f"Error searching Google Scholar by name: {e}")
            
        return publications
    
    def _load_all_publications(self):
        """Click 'Show more' button to load all publications"""
        try:
            max_attempts = 10
            attempts = 0
            
            while attempts < max_attempts:
                try:
                    # Look for "Show more" button
                    show_more_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "gsc_bpf_more"))
                    )
                    
                    if show_more_button.is_displayed() and show_more_button.is_enabled():
                        show_more_button.click()
                        time.sleep(2)
                        attempts += 1
                    else:
                        break
                        
                except Exception:
                    # No more "Show more" button or it's not clickable
                    break
                    
        except Exception as e:
            logger.debug(f"Finished loading publications: {e}")
    
    def _parse_scholar_publication_row(self, pub_element) -> Optional[Publication]:
        """Parse a single publication row from Google Scholar"""
        try:
            # Extract title
            title_element = pub_element.find_element(By.CSS_SELECTOR, "a.gsc_a_at")
            title = self.normalizer.clean_title(title_element.text)
            
            if not title:
                return None
            
            # Extract authors and journal from the second column
            details_element = pub_element.find_element(By.CSS_SELECTOR, "div.gs_gray")
            details_text = details_element.text
            
            authors = []
            journal = ""
            
            # Parse details (format: "Authors - Journal, Year")
            if " - " in details_text:
                parts = details_text.split(" - ", 1)
                authors_text = parts[0]
                venue_text = parts[1] if len(parts) > 1 else ""
                
                # Parse authors
                author_names = [name.strip() for name in authors_text.split(",")]
                for name in author_names:
                    if name:
                        authors.append(self.normalizer.normalize_author_name(name))
                
                # Extract journal and year from venue text
                if venue_text:
                    # Try to separate journal from year
                    year_match = re.search(r'(\d{4})', venue_text)
                    if year_match:
                        year_str = year_match.group(1)
                        journal = venue_text.replace(year_str, "").strip(", ")
                    else:
                        journal = venue_text
            
            # Extract year from the third column
            year = 0
            try:
                year_element = pub_element.find_element(By.CSS_SELECTOR, "span.gsc_a_h")
                year_text = year_element.text.strip()
                if year_text and year_text.isdigit():
                    year = int(year_text)
            except:
                pass
            
            # Extract citation count
            try:
                citation_element = pub_element.find_element(By.CSS_SELECTOR, "a.gsc_a_ac")
                citation_text = citation_element.text
                # This could be used for ranking/sorting later
            except:
                pass
            
            # Try to get more details by clicking on the publication
            pub_url = ""
            try:
                pub_link = title_element.get_attribute("href")
                if pub_link:
                    pub_url = pub_link
            except:
                pass
            
            # Determine publication type
            pub_type = self.normalizer.detect_publication_type(journal, journal, "")
            
            publication = Publication(
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                url=pub_url,
                type=pub_type,
                venue=journal
            )
            
            return publication
            
        except Exception as e:
            logger.error(f"Error parsing Google Scholar publication: {e}")
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