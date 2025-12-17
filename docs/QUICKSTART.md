# Quick Start Guide

Get Scrapiens running in 5 minutes.

## Setup

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows

# Verify dependencies installed
python -c "import selenium; import openai; print('✅ All OK')"
```

## Configure

```bash
# Copy environment template
copy .env.example .env

# Edit .env and add OpenAI API key:
# OPENAI_API_KEY=sk-your-key-here
```

## Update Configuration

Edit `config/config.yaml`:
```yaml
paths:
  base_dir: "C:/your/working/directory"  # Required
  input_dir: "input"
  output_dir: "all_links"
```

Edit `input/sites.yaml` - format example:
```yaml
sites:
  - name: example_site
    url: https://example.com/grants
    rss_url: https://example.com/feed.xml  # Optional: RSS for 30-50x speed
    js: false
    next_selector: null
    max_pages: 1
    pagination_param: null
```

Edit `input/keywords.yaml`:
```yaml
keywords:
  email@example.it:
    - keyword1
    - keyword2
```

## Main Commands

```bash
# Scrape all sites
python main.py scrape

# Deduplicate extracted links
python main.py deduplicate

# Classify links with AI (adds recipients)
python main.py classify

# Run full pipeline (scrape → deduplicate → classify)
python main.py pipeline
```

## Command Options

```bash
python main.py scrape -o custom_output/
python main.py classify -m gpt-4o-mini

# See all options
python main.py --help
```

## Output

After running, check:
- `all_links/` - JSON files with URLs per site
- `link_unificati.json` - Deduplicated links
- `link_unificati_classified.json` - Classified with recipients

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "OPENAI_API_KEY not found" | Add key to `.env` file |
| "Sites YAML not found" | Check path in `config/config.yaml` |
| "ChromeDriver not found" | Ensure Chrome browser is installed |

## Next Steps

- Read the full [README.md](../README.md)
- Check [examples/](../examples/) for usage patterns
- See [RSS_INTEGRATION.md](RSS_INTEGRATION.md) for RSS setup
