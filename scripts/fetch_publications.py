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
from enhanced_publication_matcher import EnhancedPublicationMatcher

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
        # Get API key from config or environment variable
        scopus_api_key = (
            config.get('api_keys', {}).get('scopus_api_key') or 
            os.getenv('SCOPUS_API_KEY')
        )
        self.scopus_fetcher = ScopusFetcher(api_key=scopus_api_key)
        self.wos_fetcher = WebOfScienceFetcher(
            api_key=os.getenv('WOS_API_KEY')
        )
        
        # Enhanced publication matcher for arXiv-centric strategy
        self.enhanced_matcher = EnhancedPublicationMatcher()
        self.google_scholar_fetcher = GoogleScholarFetcher()
    
    def fetch_all_publications(self, sources: List[str] = None) -> List[Publication]:
        """Fetch publications from all specified sources"""
        if sources is None:
            sources = ['arxiv', 'crossref', 'orcid']  # Removed 'scholar' - too slow
        
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
                for i in range(len(orcid_pubs)):
                    print(f"ORCID Publication {i+1}: {orcid_pubs[i]}")
                logger.info(f"ORCID: {len(orcid_pubs)} publications")
            except Exception as e:
                logger.error(f"Error fetching from ORCID: {e}")
        
        # Fetch from Google Scholar
        if 'scholar' in sources and self.config.get('google_scholar_id'):
            logger.info("Fetching from Google Scholar...")
            try:
                scholar_fetcher = GoogleScholarFetcher()
                scholar_pubs = scholar_fetcher.fetch_publications(
                    scholar_id=self.config['google_scholar_id']
                )
                all_publications.extend(scholar_pubs)
                logger.info(f"Google Scholar: {len(scholar_pubs)} publications")
            except Exception as e:
                logger.error(f"Error fetching from Google Scholar: {e}")
        
        # Fetch from Scopus (if API key available)
        if 'scopus' in sources:
            scopus_api_key = (
                self.config.get('api_keys', {}).get('scopus_api_key') or 
                os.getenv('SCOPUS_API_KEY')
            )
            if scopus_api_key:
                logger.info("Fetching from Scopus...")
                try:
                    # Try to fetch by author ID first, then by name
                    scopus_author_id = self.config.get('scopus_author_id')
                    if scopus_author_id:
                        scopus_pubs = self.scopus_fetcher.fetch_publications(
                            author_id=scopus_author_id
                        )
                    else:
                        scopus_pubs = self.scopus_fetcher.fetch_publications(
                            author_name=self.config['author_name']
                        )
                    all_publications.extend(scopus_pubs)
                    logger.info(f"Scopus: {len(scopus_pubs)} publications")
                except Exception as e:
                    logger.error(f"Error fetching from Scopus: {e}")
            else:
                logger.warning("Scopus requested but no API key found in config.yml or SCOPUS_API_KEY environment variable. "
                              "See scripts/SCOPUS_SETUP.md for instructions on getting an API key. Skipping Scopus.")
        
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
        
        # Debug: Check for publications with missing authors
        missing_authors = [pub for pub in all_publications if not pub.authors]
        logger.info(f"Publications with missing authors: {len(missing_authors)}")
        
        # Deduplicate publications
        deduplicated = PublicationDeduplicator.deduplicate_publications(all_publications, threshold=0.5)
        logger.info(f"Publications after deduplication: {len(deduplicated)}")
        
        # Debug: Check remaining publications with missing authors
        remaining_missing_authors = [pub for pub in deduplicated if not pub.authors]
        logger.info(f"Remaining publications with missing authors: {len(remaining_missing_authors)}")
        if remaining_missing_authors:
            for pub in remaining_missing_authors[:5]:  # Show first 5
                logger.info(f"  - Missing authors: '{pub.title}' ({pub.year}) from {pub.type}")
        
        # Sort by year (descending) and then by title
        deduplicated.sort(key=lambda p: (-p.year if p.year else 0, p.title.lower()))
        
        return deduplicated
    
    def fetch_publications_enhanced_strategy(self) -> List[Publication]:
        """
        Enhanced arXiv-centric strategy:
        1. Fetch all publications from arXiv (primary source)
        2. Fetch publications from ORCID and Scholar (for journal metadata)
        3. Match and enrich arXiv papers with journal information
        """
        logger.info("Using enhanced arXiv-centric publication fetching strategy")
        
        # Step 1: Fetch from arXiv as primary source
        logger.info("Step 1: Fetching from arXiv (primary source)...")
        arxiv_pubs = []
        try:
            arxiv_pubs = self.arxiv_fetcher.search_by_author(self.config['author_name'])
            logger.info(f"Found {len(arxiv_pubs)} publications on arXiv")
        except Exception as e:
            logger.error(f"Error fetching from arXiv: {e}")
        
        # Step 2: Fetch from ORCID for journal metadata
        logger.info("Step 2: Fetching from ORCID for journal metadata...")
        orcid_pubs = []
        if self.config.get('orcid_id'):
            try:
                orcid_pubs = self.orcid_fetcher.fetch_publications(self.config['orcid_id'])
                logger.info(f"Found {len(orcid_pubs)} publications on ORCID")
            except Exception as e:
                logger.error(f"Error fetching from ORCID: {e}")
        
        # Step 3: Fetch from Google Scholar for additional metadata
        logger.info("Step 3: Fetching from Google Scholar for additional metadata...")
        scholar_pubs = []
        if self.config.get('google_scholar_id'):
            try:
                scholar_pubs = self.google_scholar_fetcher.fetch_publications(
                    scholar_id=self.config['google_scholar_id']
                )
                logger.info(f"Found {len(scholar_pubs)} publications on Google Scholar")
            except Exception as e:
                logger.error(f"Error fetching from Google Scholar: {e}")
        
        # Step 4: Enhance arXiv publications with journal information
        logger.info("Step 4: Enriching arXiv publications with journal metadata...")
        enhanced_pubs = self.enhanced_matcher.enrich_arxiv_publications(
            arxiv_pubs, orcid_pubs, scholar_pubs
        )
        
        # Step 4.5: Ensure proper classification between preprints and journal papers
        logger.info("Step 4.5: Classifying publications as preprints vs peer-reviewed...")
        preprint_count = 0
        journal_count = 0
        for pub in enhanced_pubs:
            # Check if it has meaningful journal information (not just arXiv)
            has_real_journal = (pub.journal and pub.journal.strip() and 
                               not any(keyword in pub.journal.lower() 
                                     for keyword in ['arxiv', 'preprint', 'e-print']))
            has_doi = pub.doi and pub.doi.strip()
            
            # More specific check: if the title or journal contains "preprint", it's likely a preprint
            is_preprint_pattern = (pub.journal and 
                                 any(keyword in pub.journal.lower() 
                                   for keyword in ['preprint', 'e-print']))
            
            if has_real_journal and has_doi and not is_preprint_pattern:
                # Has real journal information and DOI - it's a peer-reviewed paper
                pub.type = "journal"
                journal_count += 1
                logger.debug(f"Classified as journal: '{pub.title[:50]}...' (journal: '{pub.journal}', doi: '{pub.doi}')")
            else:
                # arXiv-only paper or preprint - it's a preprint
                pub.type = "preprint"
                preprint_count += 1
                logger.debug(f"Classified as preprint: '{pub.title[:50]}...' (journal: '{pub.journal}', doi: '{pub.doi}')")
        
        logger.info(f"Classification results: {journal_count} journal papers, {preprint_count} preprints")
        
        # Step 5: Skip adding unmatched publications - keep arXiv-centric approach
        logger.info("Step 5: Skipping unmatched publications - using pure arXiv-centric strategy")
        
        # Skip deduplication for arXiv-centric strategy to preserve all arXiv papers
        logger.info("Skipping deduplication to preserve all arXiv publications")
        deduplicated = enhanced_pubs
        
        # Get statistics
        stats = self.enhanced_matcher.get_publication_statistics(deduplicated)
        logger.info(f"Enhanced strategy results:")
        logger.info(f"  Total publications: {stats['total']}")
        logger.info(f"  With arXiv IDs: {stats['with_arxiv']}")
        logger.info(f"  With journal info: {stats['with_journal']}")
        logger.info(f"  With DOIs: {stats['with_doi']}")
        logger.info(f"  Journal papers: {stats['journal_papers']}")
        logger.info(f"  Preprints: {stats['preprints']}")
        
        # Sort by year (descending) and then by title
        deduplicated.sort(key=lambda p: (-p.year if p.year else 0, p.title.lower()))
        
        return deduplicated
    
    def _find_unmatched_publications(self, enhanced_pubs: List[Publication], 
                                   other_pubs: List[Publication]) -> List[Publication]:
        """Find publications from other sources that weren't matched with arXiv papers"""
        unmatched = []
        
        # Get titles from enhanced publications for comparison
        enhanced_titles = {self.enhanced_matcher.normalizer.clean_title(p.title) for p in enhanced_pubs}
        
        for other_pub in other_pubs:
            other_title = self.enhanced_matcher.normalizer.clean_title(other_pub.title)
            
            # Check if this publication is already represented
            if other_title not in enhanced_titles:
                # Do a more thorough check for partial matches
                is_duplicate = False
                for enhanced_title in enhanced_titles:
                    similarity = self._calculate_title_similarity(other_title, enhanced_title)
                    if similarity > 0.85:  # High similarity threshold
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    unmatched.append(other_pub)
                    logger.debug(f"Adding unmatched publication: '{other_pub.title[:50]}...'")
        
        logger.info(f"Found {len(unmatched)} unmatched publications from other sources")
        return unmatched
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two publication titles"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, title1, title2).ratio()

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
                       default=['arxiv', 'crossref', 'orcid'],  # Removed 'scholar' - too slow
                       help='Sources to fetch from')
    parser.add_argument('--cache-file', default='publications_cache.json',
                       help='Cache file for publications')
    parser.add_argument('--update-cache-only', action='store_true',
                       help='Only update cache, do not generate files')
    parser.add_argument('--use-cache', action='store_true',
                       help='Use cached publications instead of fetching')
    parser.add_argument('--enhanced-strategy', action='store_true', default=True,
                       help='Use enhanced arXiv-centric strategy with journal metadata enrichment (default)')
    
    args = parser.parse_args()
    
    # Get script directory and site root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    site_root = os.path.dirname(script_dir)
    cache_file = os.path.join(script_dir, args.cache_file)
    
    # Load configuration - start with basic config, then merge with full config.yml
    config = load_config()
    
    # Load full config from config.yml if available
    config_path = os.path.join(script_dir, 'config.yml')
    if os.path.exists(config_path):
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f) or {}
            # Merge author info
            if 'author' in full_config:
                config.update({
                    'author_name': full_config['author'].get('name', config['author_name']),
                    'orcid_id': full_config['author'].get('orcid_id', config['orcid_id']),
                    'google_scholar_id': full_config['author'].get('google_scholar_id', config['google_scholar_id']),
                    'scopus_author_id': full_config['author'].get('scopus_author_id', ''),
                    'email': full_config['author'].get('email', config['email']),
                })
            # Add other config sections
            config.update(full_config)
    
    logger.info(f"Loaded config for author: {config['author_name']}")
    
    # Initialize aggregator and generator
    aggregator = PublicationAggregator(config)
    generator = JekyllPublicationGenerator(site_root, config)
    
    # Fetch or load publications
    if args.use_cache:
        logger.info("Loading publications from cache...")
        publications = load_publications_cache(cache_file)
    elif args.enhanced_strategy:
        logger.info("Using enhanced arXiv-centric strategy...")
        publications = aggregator.fetch_publications_enhanced_strategy()
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