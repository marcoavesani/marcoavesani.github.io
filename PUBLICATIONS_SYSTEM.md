# Automated Publication Fetcher System

## Overview

This system automatically fetches and updates your academic publications from multiple sources, generates individual publication pages, and maintains your main publications page. It's specifically configured for your GitHub Pages academic website.

## Features

✅ **Multi-source fetching**: arXiv, ORCID, CrossRef, Google Scholar, Scopus, Web of Science  
✅ **Smart deduplication**: Merges information from different sources for the same publication  
✅ **Conference paper filtering**: Excludes conference papers from display (configurable)  
✅ **Dual link display**: Shows both arXiv and journal links when available  
✅ **Jekyll integration**: Generates proper markdown files for your academic pages template  
✅ **GitHub Actions automation**: Runs daily with manual trigger option  
✅ **Caching system**: Avoids unnecessary API calls  

## Current Status

- **Total publications found**: 40 (after deduplication)
- **Displayed publications**: 39 (1 conference paper excluded)
- **Publication breakdown**:
  - Preprints: 6
  - Peer-reviewed journals: 33
  - Conference papers: 1 (excluded from display)

## Configuration

The system is configured in `scripts/config.yml`:

```yaml
author:
  name: "Marco Avesani"
  orcid: "0000-0001-5122-992X"
  # ... other settings

exclude_publication_types:
  - "conference"
```

## Files Structure

```
scripts/
├── config.yml                    # Main configuration
├── fetch_publications.py         # Main orchestrator
├── publication_utils.py          # Data structures and utilities
├── arxiv_crossref_fetcher.py     # arXiv and CrossRef integration
├── orcid_scopus_fetcher.py       # ORCID and Scopus integration
├── scholar_wos_fetcher.py        # Google Scholar and Web of Science
├── jekyll_generator.py           # Jekyll markdown generation
└── requirements.txt              # Python dependencies

_publications/                     # Generated individual publication files
_pages/publications.md            # Generated main publications page
.github/workflows/update-publications.yml  # GitHub Actions automation
```

## Usage

### Manual Update
```bash
cd scripts
python fetch_publications.py --sources arxiv orcid crossref
```

### Using Cache
```bash
python fetch_publications.py --use-cache
```

### Fetch Specific Sources
```bash
python fetch_publications.py --sources arxiv orcid
```

## Automation

The system runs automatically every day at 6 AM UTC via GitHub Actions. You can also trigger it manually from the GitHub Actions tab.

## Link Display Logic

- **Journal papers with DOI**: Shows both arXiv link and journal link (using DOI URL)
- **arXiv-only papers**: Shows only arXiv link
- **Papers without DOI**: Shows available links (arXiv, URL, etc.)

## Troubleshooting

### ORCID Parsing Errors
The system shows some parsing errors for ORCID works, but still successfully retrieves publications. These errors are for works with incomplete metadata and don't affect the final results.

### Deduplication
The system uses similarity scoring based on:
- Title matching (50% weight)
- Author overlap (20% weight)
- Year matching (10% weight)
- DOI/arXiv ID exact match (20% weight each)

Threshold is set to 0.7 for merging publications.

## Future Enhancements

- Fix ORCID parsing errors for better data quality
- Add support for additional academic sources
- Implement more sophisticated duplicate detection
- Add publication metrics integration
- Create publication statistics dashboard

---

*System implemented on September 29, 2025*
*Last tested: Publications successfully fetched and deduplicated*