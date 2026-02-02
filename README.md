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
- Date-stamped output folders for reproducibility and organization
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
  researcher1@example.com:
    - animal health
    - zoonoses
    - one health
  researcher2@example.com:
    - veterinary medicine
    - infectious diseases
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

Output files are organized in date-stamped folders:
- `intermediate_outputs/YYYYMMDD/01_scrape/all_links/` - JSON per site with URLs and keywords
- `intermediate_outputs/YYYYMMDD/02_deduplicate/link_unificati.json` - Deduplicated links
- `intermediate_outputs/YYYYMMDD/03_classify/classified_links.json` - Final classified links
- `intermediate_outputs/YYYYMMDD/04_extract/extracted_grants_*.json` - Extracted grant details
- `intermediate_outputs/YYYYMMDD/05_match_keywords/grants_by_keywords_emails_*.json` - Keyword matches
- `intermediate_outputs/YYYYMMDD/06_digests/email_digests_*.json` - Email digests

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

### Complete Command Reference

#### Full Pipeline (All Steps)

```bash
python main.py pipeline
python main.py pipeline --problematic          # Process problematic sites
python main.py pipeline -m gpt-4o              # Use different model
python main.py pipeline -v                     # Verbose logging
```

Runs all steps in sequence: **scrape → deduplicate → classify → extract → match-keywords → build-digests**

---

### Individual Commands

#### 1. Scrape

Extract links from configured websites:

```bash
python main.py scrape
python main.py scrape --problematic            # Scrape problematic sites instead
python main.py scrape -o custom_output/        # Custom output directory
python main.py scrape --save-json              # Save combined JSON file
python main.py scrape -v                       # Verbose logging
```

**Output:** JSON files per site in `intermediate_outputs/all_links/`

---

#### 2. Deduplicate

Remove duplicate links across all sources:

```bash
python main.py deduplicate
python main.py deduplicate -i input_dir/       # Custom input directory
python main.py deduplicate -o output.json      # Custom output file
python main.py deduplicate -p '*_links.txt'    # Custom file pattern
```

**Input:** Individual site JSON files  
**Output:** `intermediate_outputs/link_unificati.json`

---

#### 3. Classify

Categorize links using AI (single_grant, grant_list, other):

```bash
python main.py classify
python main.py classify -i links.json          # Custom input file
python main.py classify -o classified.json     # Custom output file
python main.py classify -m gpt-4o              # Different OpenAI model
python main.py classify -b 100                 # Custom batch size
python main.py classify --force-refresh        # Ignore cache, reclassify
```

**Input:** `intermediate_outputs/link_unificati.json`  
**Output:** `intermediate_outputs/classified_links.json`

---

#### 4. Extract

Extract detailed grant information from classified links:

```bash
python main.py extract
python main.py extract -i classified.json      # Custom input file
python main.py extract -o grants.json          # Custom output file
python main.py extract -m gpt-4o-mini          # Different model
python main.py extract -b 100                  # Batch size
python main.py extract --force-refresh         # Ignore cache
```

**Input:** `intermediate_outputs/classified_links.json`  
**Output:** `intermediate_outputs/extracted_grants_YYYYMMDD_HHMMSS.json`

---

#### 5. Match Keywords

Match extracted grants to recipients based on keywords:

```bash
python main.py match-keywords
python main.py match-keywords -i grants.json   # Custom input file
python main.py match-keywords -o output.json   # Custom output file
```

**Input:** Latest `extracted_grants_*.json`  
**Output:** `intermediate_outputs/grants_by_keywords_emails_YYYYMMDD_HHMMSS.json`

---

#### 6. Build Digests

Generate formatted email digests (HTML + plaintext) grouped by recipient:

```bash
python main.py build-digests
python main.py build-digests -i matches.json   # Custom input file
python main.py build-digests -o digest.json    # Custom output file
python main.py build-digests --template-dir custom_templates/  # Custom templates
```

**Features:**
- Groups matches by recipient email
- Renders HTML and plaintext versions
- Highlights deadlines (critical: <15 days, warning: <30 days)
- Shows matched keywords per grant
- Includes disclaimer footer

**Input:** Latest `grants_by_keywords_emails_*.json`  
**Output:** `intermediate_outputs/email_digests_YYYYMMDD_HHMMSS.json`

---

#### 7. Send Mails

Send email digests to recipients and alert summary to admin:

```bash
python main.py send-mails
python main.py send-mails --mode test          # Test mode (prompt for sample recipients)
python main.py send-mails -i digest.json       # Custom input file
python main.py send-mails --dry-run            # Simulate without sending
python main.py send-mails --skip-alert         # Skip admin alert email
```

**Modes:**
- `full` (default) - Send to all recipients in digest
- `test` - Interactive prompt to select subset of recipients

**Features:**
- Sends multipart emails (HTML + plaintext)
- Tracks failed sends
- Includes failure details in admin alert
- Collects pipeline statistics (extraction rate, match rate, send success)
- Sends summary to `scouting.bandi@izsvenezie.it`

**Credentials:** Set in `.env` file (Mailjet SMTP)

**Alert Includes:**
- Total grants extracted
- Extraction success rate
- Keyword match rate
- Number of recipients
- Failed send details with errors

---

### Help & Debug

```bash
python main.py --help                          # List all commands
python main.py <command> --help                # Help for specific command
python main.py scrape -v                       # Verbose logging (any command)
```

---

### Typical Workflow

```bash
# 1. Scrape all configured sites
python main.py scrape

# 2. Clean up duplicates
python main.py deduplicate

# 3. Classify links with AI
python main.py classify

# 4. Extract grant details
python main.py extract

# 5. Match to recipients by keywords
python main.py match-keywords

# 6. Build formatted digests
python main.py build-digests

# 7. Send emails to researchers + admin alert
python main.py send-mails
```

Or in one command:

```bash
python main.py pipeline
```

---

### Quick Commands

```bash
# Test mode: send sample emails to yourself
python main.py send-mails --mode test --dry-run

# Rebuild digests from existing matches
python main.py build-digests

# Resend last batch of digests
python main.py send-mails
```

---

### Full Pipeline

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

**Note:** EC Europa sites (`ec_calls_for_proposals`, `ec_calls_for_tenders`) are NOT configured here. They are automatically scraped via dedicated API scraper during pipeline execution or can be manually invoked with `python main.py scrape-ec-api`.

### Keywords Configuration (`input/keywords.yaml`)

```yaml
keywords:
  researcher1@example.com:
    - animal health
    - zoonoses
    - one health
    - biodiversity
  researcher2@example.com:
    - veterinary medicine
    - infectious diseases
    - public health
  researcher3@example.com:
    - climate change
    - sustainability
    - research infrastructures
```

**Field Descriptions:**
- Each key is an email address (recipient)
- Each value is a list of keywords that interest the recipient
- Classification will match grants to recipients based on keyword occurrences in grant titles/descriptions
- Keywords are case-insensitive and use word-boundary matching

Maps email addresses to keywords they're interested in. Classification will assign recipients based on keyword matches.

### Excel File (Optional) (`input/Elenco nominativi-parole chiave-siti.xlsx`)

Optional Excel file for bulk configuration. Can contain:
- **Sites sheet**: List of URLs to scrape (one per row)
- **Keywords sheet**: Email addresses with associated keywords

This file is used by `excel_reader.py` module for backward compatibility with legacy configurations. The YAML files (`sites.yaml` and `keywords.yaml`) are the recommended format.

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
  "links": [
    "https://example.com/grant/2024",
    "https://example.org/call/2025"
  ],
  "rss_metadata": {
    "https://example.com/grant/2024": {
      "title": "Research Grant 2024",
      "summary": "Funding opportunity for...",
      "published": "2024-12-15",
      "tags": [{"term": "research"}]
    }
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

Scrapiens supports RSS/Atom feed extraction for **30-50x faster scraping** with **enhanced metadata extraction and intelligent classification**.

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
- 🎯 **Smarter classification** - Uses RSS titles and descriptions
- 📊 **Full metadata** - Extracts all available RSS fields dynamically

### RSS Enhanced Pipeline

When `rss_url` is configured, Scrapiens follows a specialized pipeline:

1. **Extraction**: All RSS entry fields (title, description, date, etc.) are extracted dynamically
2. **Storage**: RSS metadata saved separately in `intermediate_outputs/rss_feeds/{site}_rss.json`
3. **Deduplication**: RSS metadata preserved during link deduplication
4. **Classification**: 
   - **Priority 1**: Domain-based rules (e.g., `ec.europa.eu` → single_grant)
   - **Priority 2**: RSS title/description pattern matching
   - **Priority 3**: Standard URL regex patterns
   - **Fallback**: LLM classification (GPT-4o-mini)

### RSS Classification Rules

Configure domain-specific rules in `config/config.yaml`:

```yaml
rss_classification:
  # Domain-based rules (highest priority)
  domain_rules:
    "ec.europa.eu/info/funding-tenders": "single_grant"
    "masaf.gov.it": "single_grant"
  
  # Title/description regex patterns
  title_patterns:
    single_grant:
      - '\b(call for proposals?|bando|grant|funding opportunity)\b'
      - '\b(fellowships?|scholarship)\b'
    grant_list:
      - '\b(bandi|grants|calls|opportunities)\b'
    other:
      - '\b(news|evento|event|conference)\b'
```

### RSS Output Format

RSS metadata file (`rss_feeds/{site}_rss.json`):

```json
[
  {
    "url": "https://example.com/call/2024",
    "title": "Call for Research Proposals 2024",
    "summary": "Applications are invited for...",
    "published": "Wed, 15 Dec 2024 10:00:00 GMT",
    "author": "Research Office",
    "tags": [{"term": "research"}],
    "id": "unique-entry-id"
    // ... all other available RSS fields
  }
]
```

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
- **[Sent Grants Implementation](docs/SENT_GRANTS_IMPLEMENTATION.md)** - Tracking system documentation
- **[Examples](examples/)** - Code examples and patterns

> **Note**: Additional implementation details and archived documentation are available in [_archive/](/_archive/) for reference.

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