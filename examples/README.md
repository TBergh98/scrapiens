# Examples

This directory contains example scripts demonstrating how to use the Scrapiens library.

## Available Examples

### 1. Single Site Scraping (`example_single_site.py`)
Demonstrates how to scrape links from a single website.

```bash
python examples/example_single_site.py
```

### 2. Batch Scraping (`example_batch_scraping.py`)
Shows how to scrape multiple websites in batch.

```bash
python examples/example_batch_scraping.py
```

### 3. Link Classification (`example_classification.py`)
Demonstrates how to classify links using OpenAI to identify research grant pages.

**Note:** Requires `OPENAI_API_KEY` to be set in `.env` file.

```bash
python examples/example_classification.py
```

### 4. Full Pipeline (`example_full_pipeline.py`)
Complete end-to-end example: scrape → deduplicate → classify.

**Note:** Requires `OPENAI_API_KEY` to be set in `.env` file.

```bash
python examples/example_full_pipeline.py
```

## Setup

Before running the examples:

1. Make sure the virtual environment is activated:
   ```bash
   .venv\Scripts\activate  # Windows
   ```

2. For classification examples, copy `.env.example` to `.env` and add your OpenAI API key:
   ```bash
   cp .env.example .env
   # Edit .env and set OPENAI_API_KEY=your_key_here
   ```

3. Update the example URLs in the scripts to match your target websites.

## Output

Examples create an `output/` directory with results:
- Individual `.txt` files for each site's links
- Combined `.json` files with all results
- Classification results with categories and confidence scores
