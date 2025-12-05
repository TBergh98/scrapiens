# Quick Start Guide

This guide will help you get Scrapiens up and running in 5 minutes.

## Step 1: Setup Environment

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows

# Verify installation
python -c "import selenium; import openai; print('All dependencies OK!')"
```

## Step 2: Configure API Key

```bash
# Copy environment template
copy .env.example .env

# Edit .env file and add your OpenAI API key:
# OPENAI_API_KEY=sk-your-actual-key-here
```

## Step 3: Update Configuration

Edit `config/config.yaml` and update the base directory and input directory:

```yaml
paths:
  base_dir: "C:/your/working/directory"  # Change this!
  input_dir: "input"
  output_dir: "all_links"
  unified_links_file: "link_unificati.json"

input_files:
  sites_file: "sites.yaml"
  keywords_file: "keywords.yaml"
```

Then edit the YAML inputs in `input/`:

`input/sites.yaml`
```yaml
sites:
  - name: esempio_universita
    url: https://www.universita-esempio.it/bandi
    js: false
    next_selector: null
    max_pages: 1
    keywords: [ricerca, bandi]
```

`input/keywords.yaml`
```yaml
keywords:
  mario@email.it:
    - ricerca
  anna@email.it:
    - bandi
```

## Step 4: Run a Quick Test

Try the single site example:

```bash
python examples/example_single_site.py
```

## Step 5: Run Your First Scrape

```bash
# Scrape websites from YAML files
python main.py scrape

# Deduplicate the results
python main.py deduplicate

# Classify the links (requires OpenAI API key)
python main.py classify
```

Or run the full pipeline:

```bash
python main.py pipeline
```

## Common Commands

```bash
python main.py scrape
python main.py scrape

# See all options
python main.py --help
```

## Expected Output

After running, you should see:
- `all_links/` directory with `.json` files (one per site, containing URLs → keywords)
- `link_unificati.json` with deduplicated links (including merged keywords)
- `link_unificati_classified.json` with AI classifications and recipients per link

## Troubleshooting

**Problem**: "OPENAI_API_KEY not found"
- **Solution**: Make sure you created `.env` file and added your API key

**Problem**: "Sites YAML file not found"
- **Solution**: Check `paths.input_dir` and `input_files.sites_file` in `config/config.yaml`

**Problem**: "ChromeDriver not found"
- **Solution**: Make sure Chrome browser is installed and updated

## Next Steps

1. Read the full [README.md](README.md) for detailed documentation
2. Check out the [examples/](examples/) directory for more usage patterns
3. Customize `config/config.yaml` for your specific needs
4. Run tests: `pytest`

## Need Help?

- Read the [README.md](README.md) for comprehensive documentation
- Check the [examples/](examples/) directory
- Open an issue on GitHub

Happy scraping! 🕷️
