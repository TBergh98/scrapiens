# Scrapiens 🕷️

A modular web scraping and AI-powered link classification system for extracting and categorizing research grant/call links from multiple websites.

> **Status**: In active development and testing  
> **Team**: Internal use (TBergh98 + collaborator)

## Technical Overview

**Web Scraping Engine**
- Selenium-based with headless Chrome
- Automatic cookie banner handling (multiple detection strategies)
- Pagination support for multi-page sites
- JavaScript rendering for dynamic content
- Overlay and popup handling

**Link Processing Pipeline**
- Deduplication across multiple sources
- OpenAI-powered classification (single_grant, grant_list, other)
- Batch processing for API efficiency
- JSON-based data interchange

**Architecture**
- Modular component design
- YAML + environment variable configuration
- Comprehensive logging system
- CLI and programmatic interfaces

## Project Structure

```
scrapiens/
├── config/                 # Configuration module
│   ├── __init__.py
│   ├── settings.py        # Configuration loader
│   └── config.yaml        # Main configuration file
├── scraper/               # Web scraping modules
│   ├── __init__.py
│   ├── sites_reader.py    # YAML sites input
│   ├── keywords_reader.py # YAML keywords/email input
│   ├── selenium_utils.py  # Cookie handling, overlays
│   ├── link_extractor.py  # Core scraping logic
│   └── pagination.py      # Pagination handling
├── processors/            # Data processing modules
│   ├── __init__.py
│   ├── deduplicator.py    # Link deduplication
│   └── classifier.py      # OpenAI classification
├── utils/                 # Utility modules
│   ├── __init__.py
│   ├── file_utils.py      # File I/O operations
│   └── logger.py          # Logging setup
├── tests/                 # Test suite
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_excel_reader.py  # YAML loader tests
│   └── test_deduplicator.py
├── examples/              # Example scripts
│   ├── README.md
│   ├── example_single_site.py
│   ├── example_batch_scraping.py
│   ├── example_classification.py
│   └── example_full_pipeline.py
├── main.py               # CLI entry point
├── requirements.txt      # Python dependencies
├── config.yaml          # Configuration file
├── .env.example         # Environment variables template
├── .gitignore
└── README.md            # This file
```

## Installation

### Prerequisites

- Python 3.7 or higher
- Chrome browser
- ChromeDriver (automatically managed by Selenium)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/TBergh98/scrapiens.git
   cd scrapiens
   ```

2. **Create and activate virtual environment:**
   ```bash
   # Windows
   py -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Create `.env` file with your OpenAI API key:
   ```bash
   OPENAI_API_KEY=sk-your-key-here
   ```

5. **Configure application:**
  Edit `config/config.yaml`:
  - Set `paths.base_dir` to your working directory
  - Ensure `paths.input_dir` points to the folder with `sites.yaml` and `keywords.yaml`
  - Optionally adjust output paths

## Configuration

### Main Configuration File (`config/config.yaml`)

```yaml
paths:
  base_dir: "/your/base/dir"
  input_dir: "input"
  output_dir: "all_links"
  unified_links_file: "link_unificati.json"

input_files:
  sites_file: "sites.yaml"
  keywords_file: "keywords.yaml"
```

selenium:
  headless: true
  implicit_wait: 15
  page_load_timeout: 30

openai:
  model: "gpt-4o-mini"
  timeout: 300
```

### Environment Variables (`.env`)

```bash
# Required for classification
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Override base directory
BASE_DIR=/your/base/dir
```

## Usage

### Command Line Interface

The project includes a comprehensive CLI for running the full pipeline or individual steps.

#### Full Pipeline

Run the complete scraping → deduplication → classification pipeline:

```bash
python main.py pipeline
```

#### Individual Commands

**1. Scrape websites (from YAML):**
```bash
python main.py scrape

# Specify custom output directory
python main.py scrape -o custom_output/
```

**2. Deduplicate links (JSON with keywords):**
```bash
python main.py deduplicate

# Specify custom input/output
python main.py deduplicate -i input_dir/ -o deduplicated.json
```

**3. Classify links (adds recipients per keyword):**
```bash
python main.py classify

# Specify custom input/output and model
python main.py classify -i links.json -o classified.json -m gpt-4o-mini
```

#### CLI Options

```bash
# See all available commands
python main.py --help

# See options for specific command
python main.py scrape --help
python main.py deduplicate --help
python main.py classify --help
python main.py pipeline --help
```

### Programmatic Usage

You can also use Scrapiens as a library in your Python code:

```python
from pathlib import Path
from config import get_config
from scraper import load_sites_from_yaml, load_keywords_from_yaml, scrape_sites
from processors import deduplicate_from_directory, LinkClassifier

config = get_config()
input_dir = config.get_full_path('paths.input_dir')
sites = load_sites_from_yaml(input_dir / config.get('input_files.sites_file'))
keywords = load_keywords_from_yaml(input_dir / config.get('input_files.keywords_file'))

# Scrape
scrape_dir = config.get_full_path('paths.output_dir')
scrape_results = scrape_sites(sites, output_dir=scrape_dir, save_individual=True)

# Deduplicate (preserves keywords)
dedup_file = config.get_full_path('paths.unified_links_file')
dedup_results = deduplicate_from_directory(scrape_dir, dedup_file)

# Classify (adds recipients)
classifier = LinkClassifier()
classifier.classify_from_file(
  input_file=dedup_file,
  output_file=dedup_file.parent / 'classified.json',
  keywords_dict=keywords
)
```

See the `examples/` directory for more detailed usage examples.

## YAML Input Format

### `input/sites.yaml`

```yaml
sites:
  - name: esempio_universita
    url: https://www.universita-esempio.it/bandi
    js: false
    next_selector: null
    max_pages: 1
    keywords: [ricerca, bandi]
```

### `input/keywords.yaml`

```yaml
keywords:
  mario@email.it:
    - ricerca
  anna@email.it:
    - bandi
```

## Output Formats

### Scraped Links (`.txt` files)

One file per site with one URL per line:

```
https://example.com/grant/2024/research-funding
https://example.com/grant/2023/innovation-award
https://example.com/about
```

### Scraped Links (`*_links.json` per site)

```json
{
  "https://example.com/grant/2024/research-funding": ["ricerca"],
  "https://example.com/grant/2023/innovation-award": ["innovazione"],
  "https://example.com/about": ["ricerca"]
}
```

### Deduplicated Links (`link_unificati.json`)

```json
{
  "links_with_keywords": {
    "https://example.com/grant/2024/research-funding": ["ricerca"],
    "https://example.org/call/doctoral-fellowship": ["innovazione", "ricerca"]
  },
  "stats": {
    "total_sites": 3,
    "total_links_before": 150,
    "unique_links": 120,
    "duplicates_removed": 30,
    "deduplication_rate": 20.0
  },
  "sites": {
    "example_com": {"url1": ["ricerca"]},
    "example_org": {"url2": ["innovazione"]}
  }
}
```

### Classified Links (`link_unificati_classified.json`)

```json
{
  "classifications": [
    {
      "url": "https://example.com/grant/2024/research-funding",
      "category": "single_grant",
      "reason": "URL contains 'grant' and specific year, likely a single grant page",
      "keywords": ["ricerca"],
      "recipients": ["mario@email.it"]
    }
  ],
  "stats": {
    "total_links": 120,
    "single_grant": 45,
    "grant_list": 30,
    "other": 45
  },
  "model": "gpt-4o-mini"
}
```

## Testing

Run the test suite using pytest:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_deduplicator.py

# Run with coverage report
pytest --cov=. --cov-report=html
```

## Technical Details

### Selenium Configuration

The scraper uses customizable Chrome options. Modify in `scraper/link_extractor.py`:

```python
chrome_options.add_argument('--window-size=1920,1080')
chrome_options.add_argument('--disable-images')
chrome_options.add_argument('--proxy-server=proxy:port')
```

### OpenAI Integration

Configurable model selection in `config/config.yaml`:

```yaml
openai:
  model: "gpt-4o-mini"  # or "gpt-4o", "gpt-3.5-turbo"
  timeout: 300
```

Batch processing is implemented for efficiency (default: 50 links per API call).

### Custom Site Handling

For sites requiring special treatment:

```python
sites = [
    {
        'name': 'complex_site',
        'url': 'https://example.com/grants',
        'js': True,  # Enable JavaScript rendering
        'next_selector': 'button.pagination-next',  # Custom pagination
        'max_pages': 5  # Limit pagination depth
    }
]
```

### Logging

Adjust log verbosity in `config/config.yaml`:

```yaml
logging:
  level: "DEBUG"  # INFO, DEBUG, WARNING, ERROR
```

---

**Repository**: https://github.com/TBergh98/scrapiens