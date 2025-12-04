# Scrapiens 🕷️

**Scrapiens** is a modular web scraping and AI-powered link classification system designed to extract and categorize research grant/call links from multiple websites.

## Features

✨ **Comprehensive Web Scraping**
- Selenium-based scraping with headless Chrome support
- Automatic cookie banner handling (multiple strategies)
- Pagination support for multi-page sites
- JavaScript rendering for dynamic content
- Overlay and popup handling

🔄 **Link Deduplication**
- Automatic removal of duplicate URLs across sites
- Detailed statistics and reporting
- JSON output format

🤖 **AI-Powered Classification**
- OpenAI integration for intelligent link categorization
- Classifies links into:
  - `single_grant`: Individual research grant/call pages
  - `grant_list`: Pages listing multiple grants
  - `other`: Generic pages (contact, about, etc.)
- Confidence scores and explanations

📊 **Production-Ready Architecture**
- Modular design with clear separation of concerns
- Comprehensive configuration system (YAML + environment variables)
- Robust logging and error handling
- Extensive test coverage
- CLI interface for easy automation

## Project Structure

```
scrapiens/
├── config/                 # Configuration module
│   ├── __init__.py
│   ├── settings.py        # Configuration loader
│   └── config.yaml        # Main configuration file
├── scraper/               # Web scraping modules
│   ├── __init__.py
│   ├── excel_reader.py    # Excel input handling
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
│   ├── test_excel_reader.py
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
   git clone https://github.com/yourusername/scrapiens.git
   cd scrapiens
   ```

2. **Create and activate virtual environment:**
   ```bash
   # Windows
   py -m venv .venv
   .venv\Scripts\activate

   # Linux/Mac
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   # Copy the example file
   cp .env.example .env
   
   # Edit .env and add your OpenAI API key
   # OPENAI_API_KEY=sk-your-key-here
   ```

5. **Configure application:**
   - Edit `config/config.yaml` to set paths, Excel file location, and scraping parameters
   - Update the `paths.base_dir` to your working directory
   - Adjust Excel row ranges if needed

## Configuration

### Main Configuration File (`config/config.yaml`)

```yaml
paths:
  base_dir: "//nas1/SCS4/UO_Biostatistica/Simonetto/Scraping"
  excel_file: "Elenco nominativi-parole chiave-siti.xlsx"
  output_dir: "all_links"
  unified_links_file: "link_unificati.json"

excel:
  sheet_index: 1
  row_ranges:
    standard: [16, 68]
    problematic: [70, 73]
  url_column: 1

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
BASE_DIR=//nas1/SCS4/UO_Biostatistica/Simonetto/Scraping
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

**1. Scrape websites:**
```bash
# Scrape standard sites (rows 16-68)
python main.py scrape

# Scrape problematic sites (rows 70-73)
python main.py scrape --problematic

# Specify custom output directory
python main.py scrape -o custom_output/
```

**2. Deduplicate links:**
```bash
# Deduplicate from default directory
python main.py deduplicate

# Specify custom input/output
python main.py deduplicate -i input_dir/ -o deduplicated.json
```

**3. Classify links:**
```bash
# Classify using default settings
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
from scraper import load_sites_from_config, scrape_sites
from processors import deduplicate_links, LinkClassifier

# Load sites from Excel
sites = load_sites_from_config(category='standard')

# Scrape sites
results = scrape_sites(sites, output_dir='output/')

# Deduplicate
dedup_results = deduplicate_links(results)

# Classify
classifier = LinkClassifier()
classifications = classifier.classify_links(dedup_results['unique_links'])
```

See the `examples/` directory for more detailed usage examples.

## Excel Input Format

The project expects an Excel file with the following structure:

- **Sheet**: Second sheet (index 1)
- **Column A**: Website URLs
- **Rows 16-68**: Standard websites
- **Rows 70-73**: Problematic websites (optional)

Example:

| A (URLs) |
|----------|
| https://example.com/grants |
| https://example.org/funding |
| https://example.net/calls |

## Output Formats

### Scraped Links (`.txt` files)

One file per site with one URL per line:

```
https://example.com/grant/2024/research-funding
https://example.com/grant/2023/innovation-award
https://example.com/about
```

### Deduplicated Links (`.json`)

```json
{
  "unique_links": [
    "https://example.com/grant/2024/research-funding",
    "https://example.org/call/doctoral-fellowship"
  ],
  "stats": {
    "total_sites": 3,
    "total_links_before": 150,
    "unique_links": 120,
    "duplicates_removed": 30,
    "deduplication_rate": 20.0
  },
  "sites": {
    "example_com": ["url1", "url2"],
    "example_org": ["url3", "url4"]
  }
}
```

### Classified Links (`.json`)

```json
{
  "classifications": [
    {
      "url": "https://example.com/grant/2024/research-funding",
      "category": "single_grant",
      "confidence": 0.95,
      "reason": "URL contains 'grant' and specific year, likely a single grant page"
    },
    {
      "url": "https://example.com/grants/list",
      "category": "grant_list",
      "confidence": 0.88,
      "reason": "URL suggests a list of multiple grants"
    }
  ],
  "stats": {
    "total_links": 120,
    "single_grant": 45,
    "grant_list": 30,
    "other": 45,
    "avg_confidence": 0.87
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

## Troubleshooting

### Common Issues

**1. ChromeDriver not found**
```
Solution: Selenium 4+ automatically manages ChromeDriver. 
Make sure Chrome browser is installed and up to date.
```

**2. OpenAI API key error**
```
Error: OPENAI_API_KEY not found
Solution: Create .env file from .env.example and add your API key
```

**3. Excel file not found**
```
Error: Excel file not found
Solution: Update paths.base_dir and paths.excel_file in config/config.yaml
```

**4. Cookie banner not detected**
```
Issue: Some cookie banners are not automatically accepted
Solution: Add custom selectors to config.yaml under cookies.attribute_selectors
```

**5. Pagination not working**
```
Issue: Script stops after first page
Solution: Set next_selector in site configuration or config.yaml
```

### Debug Mode

Enable detailed logging by setting the log level in `config/config.yaml`:

```yaml
logging:
  level: "DEBUG"  # Change from INFO to DEBUG
```

## Advanced Configuration

### Custom Site Configuration

For sites requiring special handling, you can customize the configuration:

```python
sites = [
    {
        'name': 'complex_site',
        'url': 'https://example.com/grants',
        'js': True,  # Enable JavaScript rendering
        'next_selector': 'button.pagination-next',  # Custom pagination selector
        'max_pages': 5  # Scrape up to 5 pages
    }
]
```

### Selenium Options

Customize Chrome options in `scraper/link_extractor.py`:

```python
chrome_options.add_argument('--window-size=1920,1080')
chrome_options.add_argument('--disable-images')  # Faster scraping
chrome_options.add_argument('--proxy-server=proxy:port')  # Use proxy
```

### OpenAI Model Selection

Change the AI model in `config/config.yaml`:

```yaml
openai:
  model: "gpt-4o"  # Use GPT-4 for better accuracy
  # or "gpt-3.5-turbo" for faster/cheaper processing
```

## Performance Tips

1. **Batch Processing**: Use batch classification (default 50 links per batch) to reduce API calls
2. **Headless Mode**: Keep `selenium.headless: true` for faster scraping
3. **Parallel Scraping**: Modify the scraper to use multiple browsers for parallel processing
4. **Caching**: Implement caching for previously scraped/classified links
5. **Rate Limiting**: Add delays between requests to avoid overwhelming target servers

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure all tests pass (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Support

For issues, questions, or contributions, open an issue on GitHub.

## Changelog

### Version 1.0.0 (Current)
- Initial release
- Complete web scraping pipeline
- OpenAI integration for link classification
- Comprehensive CLI interface
- Full test coverage
- Example scripts and documentation

---

**Happy Scraping! 🕷️**