# Scrapiens 🕷️

A modular web scraping and AI-powered link classification system for extracting and categorizing research grant/call links from multiple websites.

> **Status**: In active development and testing  
> **Team**: Internal use (TBergh98 + collaborator)

## Overview

**Scrapiens** streamlines the research grant discovery process:

1. **Scrape** multiple grant websites (RSS feeds or HTML)
2. **Deduplicate** links across sources while preserving keywords
3. **Classify** links by category (single grant, grant list, other) and route to recipients
4. **Export** results as structured JSON

### Technical Stack

**Web Scraping:**
- ⚡ **RSS Feed Support** - Fast extraction from RSS/Atom feeds (30-50x faster than HTML)
- 🌐 **Selenium** - Headless Chrome for dynamic JavaScript content
- 📝 **HTTP** - Direct HTTP scraping for static sites (100x faster than Selenium)
- 🔍 **Link Processing** - Cookie banner handling, overlay detection, pagination support

**Data Pipeline:**
- 🗑️ **Deduplication** - Remove duplicate links across multiple sources
- 🤖 **AI Classification** - OpenAI-powered categorization (single_grant, grant_list, other)
- 📊 **Batch Processing** - Efficient API usage and data interchange

**Architecture:**
- Modular component design with clear separation of concerns
- YAML-based configuration + environment variables
- Comprehensive logging system
- Both CLI and programmatic Python interfaces

## Quick Start

### 1. Setup

```bash
# Create virtual environment
py -m venv .venv
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Setup environment
copy .env.example .env
# Edit .env and add your OpenAI API key
```

### 2. Configure

Edit `config/config.yaml`:
```yaml
paths:
  base_dir: "C:/your/working/directory"  # Required
  input_dir: "input"
  output_dir: "all_links"
```

Edit `input/sites.yaml` - add sites to scrape:
```yaml
sites:
  - name: example_site
    url: https://example.com/grants
    rss_url: https://example.com/feed.xml  # Optional: RSS for speed
    js: false
    next_selector: null
    max_pages: 1
    pagination_param: null
```

Edit `input/keywords.yaml` - add recipients and their keywords:
```yaml
keywords:
  mario@email.it:
    - ricerca
  anna@email.it:
    - bandi
```

### 3. Run Pipeline

```bash
# Scrape all configured sites
python main.py scrape

# Deduplicate extracted links
python main.py deduplicate

# Classify links with AI (adds recipients)
python main.py classify

# Or run everything at once
python main.py pipeline
```

### 4. Check Results

Output files:
- `all_links/` - JSON per site with URLs and keywords
- `link_unificati.json` - Deduplicated links across all sites
- `link_unificati_classified.json` - Final classified links with recipients

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for more details.

## Project Structure

```
scrapiens/
├── config/                     # Configuration module
│   ├── settings.py             # Config loader
│   └── config.yaml             # Main configuration
├── scraper/                    # Web scraping modules
│   ├── rss_extractor.py        # RSS/Atom extraction
│   ├── http_extractor.py       # HTTP extraction
│   ├── selenium_utils.py       # Browser automation
│   ├── link_extractor.py       # Core scraping logic
│   └── pagination.py           # Pagination handling
├── processors/                 # Data processing
│   ├── deduplicator.py         # Remove duplicates
│   ├── classifier.py           # AI classification
│   └── site_profiles.py        # Site analysis
├── utils/                      # Utilities
│   ├── file_utils.py           # File I/O
│   ├── logger.py               # Logging
│   └── cache.py                # Caching
├── tests/                      # Test suite
├── examples/                   # Example scripts
├── docs/                       # Documentation
├── input/                      # Configuration YAML files
├── intermediate_outputs/       # Scraped links cache
├── output/                     # Final results
├── main.py                     # CLI entry point
└── requirements.txt            # Dependencies
```

## Installation & Setup

### Prerequisites

- Python 3.7+
- Chrome browser (for Selenium fallback)
- OpenAI API key (for classification)

### 1. Clone & Install

```bash
git clone https://github.com/TBergh98/scrapiens.git
cd scrapiens

py -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Environment Setup

Create `.env` file:
```bash
OPENAI_API_KEY=sk-your-key-here
# Optional
BASE_DIR=/custom/base/directory
```

### 3. Application Configuration

Edit `config/config.yaml`:

```yaml
paths:
  base_dir: "/your/base/dir"           # Where is the project?
  input_dir: "input"                   # Where are sites.yaml and keywords.yaml?
  output_dir: "all_links"              # Where to save scraped links?
  unified_links_file: "link_unificati.json"

selenium:
  headless: true
  implicit_wait: 15
  page_load_timeout: 30

openai:
  model: "gpt-4o-mini"
  timeout: 300

logging:
  level: "INFO"
```

## CLI Commands

### Full Pipeline

```bash
python main.py pipeline
```

Runs scrape → deduplicate → classify in sequence.

### Individual Steps

**Scrape:**
```bash
python main.py scrape
python main.py scrape -o custom_output/  # Custom output dir
```

**Deduplicate:**
```bash
python main.py deduplicate
python main.py deduplicate -i links_dir/ -o dedup.json
```

**Classify:**
```bash
python main.py classify
python main.py classify -m gpt-4o  # Different model
python main.py classify -i links.json -o classified.json
```

### CLI Help

```bash
python main.py --help
python main.py scrape --help
python main.py classify --help
```

## Programmatic Usage

```python
from pathlib import Path
from config import get_config
from scraper import load_sites_from_yaml, scrape_sites
from processors import deduplicate_from_directory, LinkClassifier

# Load configuration
config = get_config()
input_dir = config.get_full_path('paths.input_dir')

# Load sites and keywords
sites = load_sites_from_yaml(input_dir / 'sites.yaml')
keywords = load_keywords_from_yaml(input_dir / 'keywords.yaml')

# Scrape
scrape_dir = config.get_full_path('paths.output_dir')
scrape_results = scrape_sites(sites, output_dir=scrape_dir)

# Deduplicate
dedup_file = config.get_full_path('paths.unified_links_file')
dedup_results = deduplicate_from_directory(scrape_dir, dedup_file)

# Classify
classifier = LinkClassifier()
classifier.classify_from_file(
    input_file=dedup_file,
    output_file=dedup_file.parent / 'classified.json',
    keywords_dict=keywords
)
```

See [examples/](examples/) directory for more detailed usage patterns.

## Input Formats

### Sites Configuration (`input/sites.yaml`)

```yaml
sites:
  # Example with RSS (fast, recommended when available)
  - name: example_rss
    url: https://www.example.com/grants
    rss_url: https://www.example.com/feed.xml
    js: false
    next_selector: null
    max_pages: 1
    pagination_param: null
  
  # Example with JavaScript rendering
  - name: complex_site
    url: https://example.com/grants
    rss_url: null
    js: true
    next_selector: "button.next"
    max_pages: 5
    pagination_param: "page"
  
  # Example with standard HTTP
  - name: static_site
    url: https://example.org/grants
    rss_url: null
    js: false
    next_selector: null
    max_pages: 1
    pagination_param: null
```

**Field Descriptions:**
- `name` - Unique site identifier
- `url` - Base URL of the site
- `rss_url` - RSS feed URL (or null for HTML scraping)
- `js` - Render JavaScript? (true for dynamic content)
- `next_selector` - CSS selector for pagination button
- `max_pages` - Maximum pages to scrape
- `pagination_param` - URL parameter for pagination

### Keywords Configuration (`input/keywords.yaml`)

```yaml
keywords:
  mario@example.it:
    - ricerca
    - innovazione
  anna@example.it:
    - bandi
    - finanziamenti
```

Maps email addresses to keywords they're interested in. Classification will assign recipients based on keyword matches.

## Output Formats

### Per-Site Links

File: `all_links/{site_name}_links.json`

```json
{
  "https://example.com/grant/2024": ["ricerca", "innovazione"],
  "https://example.com/call/2025": ["ricerca"]
}
```

### Deduplicated Links

File: `link_unificati.json`

```json
{
  "links_with_keywords": {
    "https://example.com/grant/2024": ["ricerca", "innovazione"],
    "https://example.org/call/2025": ["ricerca"]
  },
  "stats": {
    "total_sites": 50,
    "total_links_before": 5000,
    "unique_links": 3500,
    "duplicates_removed": 1500,
    "deduplication_rate": 30.0
  },
  "sites": {
    "site1": {"url1": ["keyword1"]},
    "site2": {"url2": ["keyword2"]}
  }
}
```

### Classified Links

File: `link_unificati_classified.json`

```json
{
  "classifications": [
    {
      "url": "https://example.com/grant/2024",
      "category": "single_grant",
      "reason": "URL contains 'grant' with specific year, likely a single grant page",
      "keywords": ["ricerca"],
      "recipients": ["mario@example.it"]
    }
  ],
  "stats": {
    "total_links": 3500,
    "single_grant": 1200,
    "grant_list": 800,
    "other": 1500
  },
  "model": "gpt-4o-mini"
}
```

## RSS Feed Integration 🆕

Scrapiens supports RSS/Atom feed extraction for **30-50x faster scraping**.

### Quick Setup

Simply add `rss_url` to your site configuration:

```yaml
sites:
  - name: my_site
    url: https://example.com
    rss_url: https://example.com/feed.xml
    # ... other fields
```

### Benefits

- ⚡ **30-50x faster** - No browser overhead
- 🔋 **90% less resource** - No Selenium needed
- ✅ **More reliable** - Standardized XML format

### Finding RSS Feeds

Common locations:
- `/feed.xml`, `/rss.xml`, `/atom.xml`
- `/feed/`, `/blog/feed/`
- Site footer for RSS icon

Check site HTML for: `<link rel="alternate" type="application/rss+xml">`

### Documentation

See [docs/RSS_INTEGRATION.md](docs/RSS_INTEGRATION.md) for:
- Complete configuration guide
- Usage examples
- API reference
- Troubleshooting
- Performance comparison

## Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_deduplicator.py

# Verbose output
pytest -v

# Coverage report
pytest --cov=. --cov-report=html
```

## Examples

Check [examples/](examples/) directory:

- `example_single_site.py` - Scrape one site
- `example_batch_scraping.py` - Scrape multiple sites
- `example_rss_scraping.py` - Use RSS extraction
- `example_classification.py` - Classify links
- `example_full_pipeline.py` - Complete workflow

Run an example:

```bash
python examples/example_single_site.py
```

## Configuration Reference

### `config/config.yaml`

```yaml
paths:
  base_dir: "."
  input_dir: "input"
  output_dir: "all_links"
  unified_links_file: "link_unificati.json"

input_files:
  sites_file: "sites.yaml"
  keywords_file: "keywords.yaml"

selenium:
  headless: true
  implicit_wait: 15
  page_load_timeout: 30

openai:
  model: "gpt-4o-mini"
  timeout: 300

logging:
  level: "INFO"
```

### Environment Variables (`.env`)

```bash
# Required for classification
OPENAI_API_KEY=sk-...

# Optional: Override base directory
BASE_DIR=/custom/directory
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "OPENAI_API_KEY not found" | Add key to `.env` file |
| "Sites YAML not found" | Check `paths.input_dir` in config.yaml |
| "ChromeDriver not found" | Ensure Chrome browser is installed |
| "No output generated" | Check `input_dir` path and YAML file format |
| "Empty RSS results" | Verify RSS URL is correct and feed contains items |

## Technical Details

### Selenium Configuration

Customize in `scraper/link_extractor.py`:

```python
chrome_options.add_argument('--window-size=1920,1080')
chrome_options.add_argument('--disable-images')
chrome_options.add_argument('--proxy-server=proxy:port')
```

### OpenAI Model Selection

Configurable in `config/config.yaml`:

```yaml
openai:
  model: "gpt-4o-mini"  # or "gpt-4o", "gpt-3.5-turbo"
  timeout: 300
```

Uses batch processing for efficiency (default: 50 links per API call).

### Logging

Adjust verbosity in `config/config.yaml`:

```yaml
logging:
  level: "DEBUG"  # INFO, WARNING, ERROR, CRITICAL
```

## Documentation Index

- **[Quick Start](docs/QUICKSTART.md)** - Get running in 5 minutes
- **[RSS Integration Guide](docs/RSS_INTEGRATION.md)** - Setup and usage
- **[Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md)** - Technical details
- **[Examples](examples/)** - Code examples and patterns

## Performance

Performance depends on configuration:

| Scraper | Speed | Resource | Best For |
|---------|-------|----------|----------|
| **RSS** | ⚡⚡⚡ 1-2s/site | 🟢 Very Low | News feeds, structured data |
| **HTTP** | ⚡⚡ 5-15s/site | 🟡 Medium | Static sites |
| **Selenium** | ⚡ 30-60s/site | 🔴 High | Dynamic JS sites |

**Tips:**
- Use RSS when available (30-50x faster)
- Use HTTP for static sites (100x faster than Selenium)
- Use Selenium only for JavaScript-heavy sites
- Limit `max_pages` to reduce scraping time

## Development

### Project Layout

Core modules:
- `scraper/` - All scraping logic (RSS, HTTP, Selenium, pagination)
- `processors/` - Post-processing (deduplication, classification)
- `config/` - Configuration management
- `utils/` - Utilities (logging, file I/O, caching)

Tests:
- `tests/` - Pytest test suite

### Running Tests

```bash
pytest
pytest -v
pytest tests/test_deduplicator.py
pytest --cov=. --cov-report=html
```

### Adding a New Scraper

1. Create extraction function in appropriate module (`scraper/`)
2. Add to `scraper/__init__.py` exports
3. Update `scraper/link_extractor.py` routing logic if needed
4. Add unit tests in `tests/`
5. Add example in `examples/`

---

**Repository**: https://github.com/TBergh98/scrapiens  
**Status**: Active development  
**License**: See LICENSE file