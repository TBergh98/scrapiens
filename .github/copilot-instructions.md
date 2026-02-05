# Scrapiens AI Coding Guide

## Project Overview
Scrapiens is a research grant discovery pipeline that scrapes websites (RSS/HTML), deduplicates links, classifies them with OpenAI, extracts grant details, matches keywords to recipients, and generates email digests. Built for reproducibility with date-stamped outputs.

## Architecture & Data Flow

### 6-Stage Pipeline (Sequential)
Each stage writes to `intermediate_outputs/YYYYMMDD/0X_<stage>/`:

1. **01_scrape** → Scrapes sites via RSS (fast) or Selenium/HTTP fallback → `all_links/*.json`
2. **02_deduplicate** → Merges & dedupes → `link_unificati.json`
3. **03_classify** → OpenAI categorizes as `single_grant`/`grant_list`/`other` → `classified_links.json`
4. **04_extract** → Scrapes grant details (title, deadline, description) → `extracted_grants_*.json`
5. **05_match_keywords** → Maps grants to recipients by keywords → `grants_by_keywords_emails_*.json`
6. **06_digests** → Builds HTML/text email templates → `email_digests_*.json`

### Run Date Management (Critical!)
- **Full pipeline**: Always creates NEW date folder (e.g., `20260205/`)
- **Individual steps**: Continue MOST RECENT incomplete run OR create new folder
- Logic in `utils/run_date_manager.py` - uses `RunDateManager.get_current_run_date()`
- All steps in same run share the same date folder for reproducibility

### Configuration System
- `config/config.yaml` - All paths, timeouts, scraping behavior
- `input/sites.yaml` - Sites to scrape (`rss_url` enables fast RSS path)
- `input/keywords.yaml` - Recipient emails + keywords for matching
- Environment: `.env` file for `OPENAI_API_KEY`, `BASE_DIR` override
- Config accessed via singleton: `from config import get_config; config = get_config()`

## Key Patterns & Conventions

### RSS-First Extraction Strategy
**Routing logic in `scraper/link_extractor.py:scrape_site()`:**
```python
# If site has rss_url → Use RssExtractor (30-50x faster)
# Else → Use Selenium/HTTP extraction
if site_config.get('rss_url'):
    return RssExtractor.scrape_site_rss(...)
```
**Classification**: RSS uses REGEX on title field (no LLM); HTML uses OpenAI
- Config: `config.yaml` section `rss_classification.patterns.*`
- Fallback: If no title match → URL-based classification

### Deduplication & History
- **Cross-run tracking**: `intermediate_outputs/seen_urls.json` stores URLs from all past runs
- **Default behavior**: Filter out previously seen URLs (avoids re-sending)
- **Override**: `python main.py scrape --ignore-history` or interactive prompt
- Manager: `utils.seen_urls_manager.SeenUrlsManager`

### OpenAI Integration
- **Classifier**: `processors/classifier.py:LinkClassifier` - batch processing with cache
- **Extractor**: `processors/extractor.py:GrantExtractor` - parallel scraping with retries
- Model configurable: `--model gpt-4o-mini` (default) or `gpt-4o`
- Caching: `utils/cache.py` stores API responses to avoid re-processing

### Logging & Progress
- Centralized: `utils/logger.py` with `setup_logger()` and `get_logger(__name__)`
- Timed operations: `@timed_operation("description")` decorator
- Milestones: `log_milestone("🎯 Important event")` for pipeline stages
- Emojis used extensively: 🔔 RSS, 🌐 Selenium, ⚡ HTTP, 📊 stats, ✅ success

## Development Workflows

### Running Pipeline
```bash
# Full pipeline (creates new date folder)
python main.py pipeline

# Individual steps (continues incomplete run)
python main.py scrape           # Step 1
python main.py deduplicate      # Step 2
python main.py classify         # Step 3
python main.py extract          # Step 4
python main.py match-keywords   # Step 5
python main.py build-digests    # Step 6
python main.py send-mails       # Email sending (separate)

# EC Europa API (dedicated source)
python main.py scrape-ec-api    # Bulk fetch
python main.py extract-ec-api   # Fetch descriptions
```

### Testing
- Framework: pytest in `tests/`
- Run: `pytest` or `pytest -v tests/test_specific.py`
- Fixtures: `tests/conftest.py` provides sample data
- Integration tests: `tests/test_rss_integration.py`, `tests/verify_rss_integration.py`

### Adding a New Site
1. Add to `input/sites.yaml`:
   ```yaml
   - name: new_site
     url: https://example.com/grants
     rss_url: https://example.com/feed.xml  # Optional: enables fast path
     js: false      # true = Selenium, false = HTTP
     next_selector: ".pagination .next"  # CSS selector for pagination
     max_pages: 5   # Limit pagination
   ```
2. Test: `python main.py scrape` (outputs to `intermediate_outputs/YYYYMMDD/01_scrape/all_links/new_site_links.json`)

### Debugging Scraping Issues
- Enable verbose logging: `python main.py scrape --verbose` (sets DEBUG level)
- Check logs: `scrapiens.log` in project root
- Cookie banners: Auto-handled via `selenium_utils.accept_cookies()` (config: `config.yaml:cookies.*`)
- JS sites: Set `js: true` in sites.yaml → uses Selenium with scrolling

## Important Constraints

### Date Folder Chain Dependencies
When running individual steps, previous steps MUST exist in the run folder:
- `02_deduplicate` requires `01_scrape/all_links/`
- `03_classify` requires `02_deduplicate/link_unificati.json`
- `04_extract` requires `03_classify/classified_links.json`
- `05_match_keywords` requires `04_extract/extracted_grants_*.json`
- `06_digests` requires `05_match_keywords/grants_by_keywords_emails_*.json`

### Path Handling
- **Always use `Path` objects** from `pathlib` (not string concatenation)
- **Cross-platform**: Config uses forward slashes (`/`) in YAML, `Path` handles conversion
- **Absolute paths**: Most functions expect absolute paths via `config.get_full_path()`

### Selenium Specifics
- **Page load strategy**: `eager` (stops when DOM ready, not on full resource load)
- **Cookie banners**: Auto-detected and clicked via text patterns + CSS selectors
- **Pagination**: `scraper/pagination.py` handles click-based and URL-param pagination
- **Headless**: Default `true` (config: `selenium.headless`)

## Code Organization

### Module Responsibilities
- `scraper/` - Link extraction (RSS, HTTP, Selenium), site config readers, EC Europa API
- `processors/` - Classification, extraction, deduplication, digest building, email matching
- `utils/` - Logging, caching, file I/O, run date management, seen URLs tracking
- `config/` - YAML config loading with env overrides, singleton `get_config()`
- `templates/` - Jinja2 email templates (HTML/text)

### Data Structures
**Scraper output** (`01_scrape/*.json`):
```json
{
  "url": "https://example.com/grant123",
  "keywords": ["keyword1", "keyword2"],
  "metadata": {"title": "...", "published": "..."}  // RSS only
}
```

**Classified output** (`03_classify/classified_links.json`):
```json
{
  "classifications": [
    {"url": "...", "category": "single_grant", "reasoning": "..."}
  ],
  "stats": {"single_grant": 10, "grant_list": 5, "other": 2}
}
```

**Extracted output** (`04_extract/extracted_grants_*.json`):
```json
{
  "grants": [
    {
      "url": "...",
      "title": "Research Grant 2024",
      "deadline": "2024-12-31",
      "abstract": "...",
      "recipients": ["email1@example.com"],
      "matched_keywords": ["keyword1"],
      "extraction_success": true
    }
  ],
  "stats": {...}
}
```

## Common Pitfalls

1. **Don't modify config during runtime** - Config is singleton, changes won't persist
2. **Check run date folder exists** - Individual steps fail if prior step missing
3. **RSS classification is REGEX-only** - No LLM for RSS (see `config.yaml:rss_classification`)
4. **Selenium timeouts** - Use `eager` page load, not `normal` (prevents infinite waits)
5. **Deduplication scope** - Only within same run; cross-run handled by `seen_urls.json`

## File Naming Conventions
- Scraped links: `<sitename>_links.json`
- Unified links: `link_unificati.json`
- Classified: `classified_links.json`
- Extracted: `extracted_grants_<timestamp>.json`
- Matched: `grants_by_keywords_emails_<timestamp>.json`
- Digests: `email_digests_<timestamp>.json`
