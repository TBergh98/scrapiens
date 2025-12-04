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

Edit `config/config.yaml` and update the base directory:

```yaml
paths:
  base_dir: "C:/your/working/directory"  # Change this!
  excel_file: "Elenco nominativi-parole chiave-siti.xlsx"
```

## Step 4: Run a Quick Test

Try the single site example:

```bash
python examples/example_single_site.py
```

## Step 5: Run Your First Scrape

```bash
# Scrape websites from Excel file
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
# Scrape standard sites
python main.py scrape

# Scrape problematic sites
python main.py scrape --problematic

# See all options
python main.py --help
```

## Expected Output

After running, you should see:
- `all_links/` directory with `.txt` files (one per site)
- `link_unificati.json` with deduplicated links
- `link_unificati_classified.json` with AI classifications

## Troubleshooting

**Problem**: "OPENAI_API_KEY not found"
- **Solution**: Make sure you created `.env` file and added your API key

**Problem**: "Excel file not found"
- **Solution**: Update `paths.base_dir` in `config/config.yaml`

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
