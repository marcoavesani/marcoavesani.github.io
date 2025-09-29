# Academic Publication Auto-Fetcher

This system automatically fetches and updates your academic publications from multiple sources including arXiv, CrossRef, ORCID, Google Scholar, Scopus, and Web of Science. It generates Jekyll-compatible markdown files for your academic website.

## 🚀 Quick Start

1. **Run the setup script:**
   ```bash
   cd scripts
   python setup.py
   ```

2. **Configure your details:**
   Edit `scripts/config.yml` with your academic profile information.

3. **Test the fetcher:**
   ```bash
   python scripts/fetch_publications.py --sources arxiv orcid
   ```

4. **Check the results:**
   - Individual publication files: `_publications/`
   - Main publications page: `_pages/publications.md`

## 📋 Features

### 🔍 Multiple Data Sources
- **arXiv**: Preprints in physics, mathematics, computer science, etc.
- **CrossRef**: DOI-registered publications from academic publishers
- **ORCID**: Your researcher profile publications
- **Google Scholar**: Comprehensive academic search (requires Chrome/Selenium)
- **Scopus**: Elsevier's abstract and citation database (API key required)
- **Web of Science**: Clarivate's research database (API key required)

### 🔄 Smart Deduplication
- Automatically detects and merges duplicate publications across sources
- Combines information from multiple sources for complete records
- Prefers journal versions over preprints when both exist

### 📝 Jekyll Integration
- Generates individual markdown files for each publication
- Updates main publications page with categorized listings
- Compatible with Academic Pages template
- Supports custom styling and layouts

### ⚡ Automated Updates
- GitHub Actions workflow for daily updates
- Caching system for faster subsequent runs
- Configurable scheduling and sources

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher
- Jekyll-based academic website (like Academic Pages)
- Chrome browser (for Google Scholar fetching)

### Setup
1. **Clone or copy the scripts to your Jekyll site:**
   ```bash
   # If starting fresh, create the scripts directory
   mkdir scripts
   cd scripts
   
   # Copy all the Python files to this directory
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure your settings:**
   Edit `config.yml` with your academic information:
   ```yaml
   author:
     name: "Your Name"
     orcid_id: "0000-0000-0000-0000"
     google_scholar_id: "your-scholar-id"
   ```

## 📖 Usage

### Basic Usage
```bash
# Fetch from all default sources
python fetch_publications.py

# Fetch from specific sources
python fetch_publications.py --sources arxiv crossref orcid

# Use cached data (faster for development)
python fetch_publications.py --use-cache

# Update cache only (don't generate files)
python fetch_publications.py --update-cache-only
```

### Advanced Options
```bash
# Custom cache file
python fetch_publications.py --cache-file my_publications.json

# Multiple sources
python fetch_publications.py --sources arxiv crossref orcid scholar scopus
```

## ⚙️ Configuration

The `config.yml` file contains all configuration options:

### Author Information
```yaml
author:
  name: "Marco Avesani"
  highlight_name: "M. Avesani"  # How to highlight your name
  orcid_id: "0000-0001-5122-992X"
  google_scholar_id: "g9RL-QcAAAAJ"
  email: "marco.avesani@unipd.it"
```

### Fetching Settings
```yaml
fetching:
  default_sources: ["arxiv", "crossref", "orcid", "scholar"]
  max_results_per_source: 200
  deduplication_threshold: 0.8
```

### Publication Categories
```yaml
publication_types:
  preprint:
    display_name: "Preprints"
  journal:
    display_name: "Peer-reviewed Journals"
  conference:
    display_name: "Conference Papers"
```

## 🤖 Automation with GitHub Actions

The included workflow (`/.github/workflows/update-publications.yml`) automatically:

1. **Runs daily** at 6 AM UTC (configurable)
2. **Fetches new publications** from all sources
3. **Updates your website** if changes are found
4. **Commits changes** automatically

### Manual Workflow Triggers
You can manually trigger the workflow from GitHub's Actions tab with options:
- **Sources**: Choose which sources to fetch from
- **Force update**: Update even if no changes detected

### Setup GitHub Actions
1. **Enable Actions** in your repository settings
2. **Add API keys** as repository secrets (optional):
   - `SCOPUS_API_KEY`: For Scopus access
   - `WOS_API_KEY`: For Web of Science access

## 🔑 API Keys (Optional)

### Scopus API Key
1. Register at [Elsevier Developer Portal](https://dev.elsevier.com/)
2. Create an application to get API key
3. Add as `SCOPUS_API_KEY` environment variable or GitHub secret

### Web of Science API Key
1. Requires institutional subscription
2. Contact your librarian for access
3. Add as `WOS_API_KEY` environment variable or GitHub secret

## 📁 File Structure

```
your-jekyll-site/
├── _config.yml                 # Jekyll configuration
├── _pages/
│   └── publications.md         # Main publications page (auto-updated)
├── _publications/              # Individual publication files (auto-generated)
│   ├── author_2023_title.md
│   └── ...
├── scripts/                    # Publication fetcher
│   ├── config.yml             # Fetcher configuration
│   ├── fetch_publications.py  # Main script
│   ├── setup.py              # Setup and validation
│   ├── requirements.txt      # Python dependencies
│   └── ...
└── .github/workflows/
    └── update-publications.yml # GitHub Actions workflow
```

## 🔧 Customization

### Custom Publication Templates
Edit the `generate_markdown_content()` method in `publication_utils.py` to customize:
- Publication page layout
- Metadata fields
- Button styles
- Citation formats

### Custom Venue Mappings
Add venue name standardization in `config.yml`:
```yaml
venue_mappings:
  "Phys. Rev. A": "Physical Review A"
  "Nat. Commun.": "Nature Communications"
```

### Filtering Options
Configure in `config.yml`:
```yaml
filters:
  min_year: 2020  # Only publications from 2020 onwards
  exclude_venues: ["Workshop on X"]  # Exclude certain venues
  only_first_last_author: true  # Only first/last author publications
```

## 🐛 Troubleshooting

### Common Issues

**"No publications found"**
- Check your ORCID ID and Google Scholar ID in config.yml
- Try fetching from a single source first: `--sources orcid`
- Check the log output for API errors

**"Chrome driver not found" (Google Scholar)**
- Install Chrome browser
- The script automatically downloads ChromeDriver
- For headless servers, ensure Chrome is installed

**"API rate limit exceeded"**
- Some sources have rate limits
- The script includes delays, but you might need to run less frequently
- Use caching to avoid repeated requests

**"Permission denied" errors**
- Make sure you have write permissions to the Jekyll directories
- For GitHub Actions, ensure the workflow has necessary permissions

### Debug Mode
```bash
# Enable verbose logging
python fetch_publications.py --sources arxiv orcid 2>&1 | tee debug.log
```

## 📊 Output Format

### Individual Publication Files
Each publication gets its own markdown file in `_publications/`:

```markdown
---
title: "Publication Title"
collection: publications
permalink: /publication/citation-key
excerpt: 'Brief abstract...'
date: 2023-01-01
venue: 'Journal Name'
paperurl: 'https://doi.org/...'
citation: 'Authors, "Title", Journal (2023)'
---

Full abstract here...

**Authors:** M. Avesani, Co-Author

[ArXiv](https://arxiv.org/abs/...) [Journal](https://doi.org/...)
```

### Main Publications Page
The `_pages/publications.md` file is updated with categorized listings:

```markdown
## Preprints

* **M. Avesani**, H. Tebyanian, ... - *"Title"* - arXiv:2010.05798 (2023)
  [ArXiv](https://arxiv.org/abs/2010.05798)

## Peer-reviewed Journals

* **M. Avesani**, L. Calderaro, ... - *"Title"* - Nature Communications (2023)
  [Journal](https://doi.org/...)
```

## 🤝 Contributing

Feel free to:
- Report bugs or issues
- Suggest new features
- Add support for additional academic databases
- Improve the deduplication algorithms
- Enhance the Jekyll integration

## 📄 License

This project is open source and available under the MIT License.

## 🙋 Support

If you encounter issues:
1. Check this README for troubleshooting tips
2. Look at the configuration examples
3. Run the setup script to validate your installation
4. Check the GitHub Actions logs for automation issues

The system is designed to be robust and handle various edge cases, but academic databases can be unpredictable. The caching system helps ensure you don't lose progress if something goes wrong.