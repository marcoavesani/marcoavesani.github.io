#!/usr/bin/env python3
"""
Main script to fetch publications from multiple academic sources and update Jekyll site
"""

import os
import sys
import json
import logging
from typing import List, Dict, Set
from datetime import datetime
import argparse

# Add the scripts directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from publication_utils import (
    Publication, PublicationDeduplicator, load_config, 
    save_publications_cache, load_publications_cache
)
from arxiv_crossref_fetcher import ArxivFetcher, CrossRefFetcher, DOIFetcher
from orcid_scopus_fetcher import ORCIDFetcher, ScopusFetcher
from scholar_wos_fetcher import GoogleScholarFetcher, WebOfScienceFetcher

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PublicationAggregator:
    """Aggregate publications from multiple sources"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.publications = []
        
        # Initialize fetchers
        self.arxiv_fetcher = ArxivFetcher()
        self.crossref_fetcher = CrossRefFetcher()
        self.doi_fetcher = DOIFetcher()
        self.orcid_fetcher = ORCIDFetcher()
        
        # Initialize optional fetchers (require API keys or special setup)
        self.scopus_fetcher = ScopusFetcher(
            api_key=os.getenv('d78321743b25613d83bf3c86729de007')
        )
        self.wos_fetcher = WebOfScienceFetcher(
            api_key=os.getenv('WOS_API_KEY')
        )
    
    def fetch_all_publications(self, sources: List[str] = None) -> List[Publication]:
        """Fetch publications from all specified sources"""
        if sources is None:
            sources = ['arxiv', 'crossref', 'orcid', 'scholar']
        
        all_publications = []
        
        # Fetch from arXiv
        if 'arxiv' in sources:
            logger.info("Fetching from arXiv...")
            try:
                arxiv_pubs = self.arxiv_fetcher.search_by_author(
                    self.config['author_name']
                )
                all_publications.extend(arxiv_pubs)
                logger.info(f"ArXiv: {len(arxiv_pubs)} publications")
            except Exception as e:
                logger.error(f"Error fetching from arXiv: {e}")
        
        # Fetch from CrossRef
        if 'crossref' in sources:
            logger.info("Fetching from CrossRef...")
            try:
                crossref_pubs = self.crossref_fetcher.search_by_author(
                    self.config['author_name']
                )
                all_publications.extend(crossref_pubs)
                logger.info(f"CrossRef: {len(crossref_pubs)} publications")
            except Exception as e:
                logger.error(f"Error fetching from CrossRef: {e}")
        
        # Fetch from ORCID
        if 'orcid' in sources and self.config.get('orcid_id'):
            logger.info("Fetching from ORCID...")
            try:
                orcid_pubs = self.orcid_fetcher.fetch_publications(
                    self.config['orcid_id']
                )
                all_publications.extend(orcid_pubs)
                logger.info(f"ORCID: {len(orcid_pubs)} publications")
            except Exception as e:
                logger.error(f"Error fetching from ORCID: {e}")
        
        # Fetch from Google Scholar
        if 'scholar' in sources and self.config.get('google_scholar_id'):
            logger.info("Fetching from Google Scholar...")
            try:
                with GoogleScholarFetcher() as scholar_fetcher:
                    scholar_pubs = scholar_fetcher.fetch_publications(
                        scholar_id=self.config['google_scholar_id']
                    )
                    all_publications.extend(scholar_pubs)
                    logger.info(f"Google Scholar: {len(scholar_pubs)} publications")
            except Exception as e:
                logger.error(f"Error fetching from Google Scholar: {e}")
        
        # Fetch from Scopus (if API key available)
        if 'scopus' in sources and os.getenv('SCOPUS_API_KEY'):
            logger.info("Fetching from Scopus...")
            try:
                scopus_pubs = self.scopus_fetcher.fetch_publications(
                    author_name=self.config['author_name']
                )
                all_publications.extend(scopus_pubs)
                logger.info(f"Scopus: {len(scopus_pubs)} publications")
            except Exception as e:
                logger.error(f"Error fetching from Scopus: {e}")
        
        # Fetch from Web of Science (if API key available)
        if 'wos' in sources and os.getenv('WOS_API_KEY'):
            logger.info("Fetching from Web of Science...")
            try:
                wos_pubs = self.wos_fetcher.fetch_publications(
                    self.config['author_name']
                )
                all_publications.extend(wos_pubs)
                logger.info(f"Web of Science: {len(wos_pubs)} publications")
            except Exception as e:
                logger.error(f"Error fetching from Web of Science: {e}")
        
        logger.info(f"Total publications before deduplication: {len(all_publications)}")
        
        # Debug: Check for potential duplicates
        titles = [pub.title.lower().strip() for pub in all_publications]
        title_counts = {}
        for title in titles:
            title_counts[title] = title_counts.get(title, 0) + 1
        
        potential_duplicates = {title: count for title, count in title_counts.items() if count > 1}
        if potential_duplicates:
            logger.info(f"Potential duplicates by title: {potential_duplicates}")
        
        # Deduplicate publications
        deduplicated = PublicationDeduplicator.deduplicate_publications(all_publications, threshold=0.7)
        logger.info(f"Publications after deduplication: {len(deduplicated)}")
        
        # Sort by year (descending) and then by title
        deduplicated.sort(key=lambda p: (-p.year if p.year else 0, p.title.lower()))
        
        return deduplicated

class JekyllPublicationGenerator:
    """Generate Jekyll markdown files for publications"""
    
    def __init__(self, site_root: str, config: Dict):
        self.site_root = site_root
        self.config = config
        self.publications_dir = os.path.join(site_root, '_publications')
        self.pages_dir = os.path.join(site_root, '_pages')
    
    def generate_publication_files(self, publications: List[Publication]):
        """Generate individual markdown files for each publication"""
        # Filter publications based on configuration
        filtered_publications = self._filter_publications(publications)
        
        # Create publications directory if it doesn't exist
        os.makedirs(self.publications_dir, exist_ok=True)
        
        # Clear existing publication files
        self._clear_existing_files()
        
        for pub in filtered_publications:
            self._generate_publication_file(pub)
        
        logger.info(f"Generated {len(filtered_publications)} publication files")
    
    def update_publications_page(self, publications: List[Publication]):
        """Update the main publications page"""
        publications_page = os.path.join(self.pages_dir, 'publications.md')
        
        # Filter publications based on configuration
        filtered_publications = self._filter_publications(publications)
        
        # Group publications by type
        grouped_pubs = self._group_publications_by_type(filtered_publications)
        
        # Generate markdown content
        content = self._generate_publications_page_content(grouped_pubs)
        
        # Write to file
        with open(publications_page, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info("Updated publications.md page")
    
    def _clear_existing_files(self):
        """Clear existing publication files"""
        if os.path.exists(self.publications_dir):
            for filename in os.listdir(self.publications_dir):
                if filename.endswith('.md'):
                    os.remove(os.path.join(self.publications_dir, filename))
    
    def _filter_publications(self, publications: List[Publication]) -> List[Publication]:
        """Filter publications based on configuration settings"""
        filtered = []
        
        # Load filter settings from config or set defaults
        try:
            from publication_utils import load_config
            full_config = load_config()
            
            # Get the full config with custom settings if available
            config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
            if os.path.exists(config_path):
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    full_config.update(yaml.safe_load(f) or {})
            
            exclude_types = full_config.get('filters', {}).get('exclude_publication_types', [])
        except Exception:
            exclude_types = ['conference']  # Default to excluding conference papers
        
        for pub in publications:
            # Filter by publication type
            if pub.type.lower() in [t.lower() for t in exclude_types]:
                continue
                
            filtered.append(pub)
        
        return filtered
    
    def _generate_publication_file(self, pub: Publication):
        """Generate markdown file for a single publication"""
        filename = f"{pub.get_citation_key()}.md"
        filepath = os.path.join(self.publications_dir, filename)
        
        content = pub.generate_markdown_content(self.config['author_name'])
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _group_publications_by_type(self, publications: List[Publication]) -> Dict[str, List[Publication]]:
        """Group publications by type"""
        grouped = {
            'preprint': [],
            'journal': [],
            'conference': [],
            'book': [],
            'other': []
        }
        
        for pub in publications:
            pub_type = pub.type.lower()
            if pub_type in grouped:
                grouped[pub_type].append(pub)
            else:
                grouped['other'].append(pub)
        
        return grouped
    
    def _generate_publications_page_content(self, grouped_pubs: Dict[str, List[Publication]]) -> str:
        """Generate content for the main publications page"""
        content = f"""---
layout: archive
title: "Publications"
permalink: /publications/
author_profile: true
---

{{%if author.googlescholar %}}
  You can also find my articles on <u><a href="{{{{author.googlescholar}}}}">my Google Scholar profile</a>.</u>
{{%endif %}}

{{%include base_path %}}

*Last updated: {datetime.now().strftime('%B %d, %Y')}*

"""
        
        # Add preprints section
        if grouped_pubs['preprint']:
            content += "## Preprints\n\n"
            for pub in grouped_pubs['preprint']:
                content += self._format_publication_entry(pub) + "\n\n"
        
        # Add peer-reviewed journals section
        if grouped_pubs['journal']:
            content += "## Peer-reviewed Journals\n\n"
            for pub in grouped_pubs['journal']:
                content += self._format_publication_entry(pub) + "\n\n"
        
        # Conference papers section - excluded per user request
        
        # Add books/chapters section
        if grouped_pubs['book']:
            content += "## Books and Book Chapters\n\n"
            for pub in grouped_pubs['book']:
                content += self._format_publication_entry(pub) + "\n\n"
        
        # Add other publications section
        if grouped_pubs['other']:
            content += "## Other Publications\n\n"
            for pub in grouped_pubs['other']:
                content += self._format_publication_entry(pub) + "\n\n"
        
        return content
    
    def _format_publication_entry(self, pub: Publication) -> str:
        """Format a single publication entry for the list"""
        # Format: Authors - "Title" - Journal/Venue (Year)
        authors_str = pub.format_authors(self.config['author_name'])
        venue_str = pub.venue or pub.journal
        
        entry = f"* {authors_str} - *\"{pub.title}\"*"
        
        if venue_str:
            entry += f" - {venue_str}"
        
        if pub.year:
            entry += f" ({pub.year})"
        
        entry += " \\\\"
        
        # Add links - always show both arXiv and journal for journal papers
        links = []
        
        # Always add arXiv link if available
        if pub.arxiv_id:
            arxiv_url = f"https://arxiv.org/abs/{pub.arxiv_id}"
            links.append(f"[ArXiv]({arxiv_url}){{: .btn .btn--info}}")
        
        # For journal papers, prioritize DOI link, then regular URL
        if pub.type.lower() == 'journal':
            journal_url = None
            if pub.doi:
                journal_url = f"https://doi.org/{pub.doi}"
            elif pub.url and pub.url != f"https://arxiv.org/abs/{pub.arxiv_id}":
                journal_url = pub.url
                
            if journal_url:
                links.append(f"[Journal]({journal_url}){{: .btn .btn--info}}")
        elif pub.url and pub.url != f"https://arxiv.org/abs/{pub.arxiv_id}":
            # For non-journal papers, show regular URL
            links.append(f"[Paper]({pub.url}){{: .btn .btn--info}}")
        
        # Add PDF link if available and different from arXiv PDF
        if pub.pdf_url and (not pub.arxiv_id or pub.pdf_url != f"https://arxiv.org/pdf/{pub.arxiv_id}.pdf"):
            links.append(f"[PDF]({pub.pdf_url}){{: .btn .btn--info}}")
        
        if links:
            entry += "\n" + "  ".join(links)
        
        return entry

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Fetch and update academic publications')
    parser.add_argument('--sources', nargs='+', 
                       choices=['arxiv', 'crossref', 'orcid', 'scholar', 'scopus', 'wos'],
                       default=['arxiv', 'crossref', 'orcid', 'scholar'],
                       help='Sources to fetch from')
    parser.add_argument('--cache-file', default='publications_cache.json',
                       help='Cache file for publications')
    parser.add_argument('--update-cache-only', action='store_true',
                       help='Only update cache, do not generate files')
    parser.add_argument('--use-cache', action='store_true',
                       help='Use cached publications instead of fetching')
    
    args = parser.parse_args()
    
    # Get script directory and site root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    site_root = os.path.dirname(script_dir)
    cache_file = os.path.join(script_dir, args.cache_file)
    
    # Load configuration
    config = load_config()
    logger.info(f"Loaded config for author: {config['author_name']}")
    
    # Initialize aggregator and generator
    aggregator = PublicationAggregator(config)
    generator = JekyllPublicationGenerator(site_root, config)
    
    # Fetch or load publications
    if args.use_cache:
        logger.info("Loading publications from cache...")
        publications = load_publications_cache(cache_file)
    else:
        logger.info("Fetching publications from sources...")
        publications = aggregator.fetch_all_publications(args.sources)
        
        # Save to cache
        save_publications_cache(publications, cache_file)
    
    if not publications:
        logger.warning("No publications found")
        return
    
    logger.info(f"Processing {len(publications)} publications")
    
    # Generate files unless cache-only mode
    if not args.update_cache_only:
        generator.generate_publication_files(publications)
        generator.update_publications_page(publications)
        logger.info("Publication files generated successfully")
    
    # Print summary
    print(f"\nSummary:")
    print(f"  Total publications: {len(publications)}")
    
    by_type = {}
    for pub in publications:
        by_type[pub.type] = by_type.get(pub.type, 0) + 1
    
    for pub_type, count in by_type.items():
        print(f"  {pub_type.title()}: {count}")
    
    print(f"  Cache file: {cache_file}")
    
    if not args.update_cache_only:
        print(f"  Publications directory: {generator.publications_dir}")
        print(f"  Publications page: {os.path.join(generator.pages_dir, 'publications.md')}")

if __name__ == "__main__":
    main()