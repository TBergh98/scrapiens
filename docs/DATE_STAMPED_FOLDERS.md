# Date-Stamped Output Folders

## Overview

Every pipeline run (full or partial) now organizes all intermediate outputs into date-stamped subfolders within `intermediate_outputs/`. This ensures:

- **Reproducibility**: Each run's outputs are kept together
- **Organization**: Easy to track multiple runs over time
- **Continuity**: Partial runs can complete incomplete runs from the same date

## Folder Structure

```
intermediate_outputs/
├── 20260101/              # Run from January 1, 2026
│   ├── 01_scrape/
│   │   ├── all_links/     # Scraped links
│   │   └── rss_feeds/     # RSS metadata
│   ├── 02_deduplicate/
│   │   └── link_unificati.json
│   ├── 03_classify/
│   │   └── classified_links.json
│   ├── 04_extract/
│   │   ├── extracted_grants_20260101_143522.json
│   │   ├── site_profiles.json
│   │   └── grants_cache.json
│   ├── 05_match_keywords/
│   │   └── grants_by_keywords_emails_20260101_143525.json
│   └── 06_digests/
│       └── email_digests_20260101_143527.json
├── 20260127/              # Run from January 27, 2026
│   └── ...
└── seen_urls.json         # Cross-run URL tracking (not dated)
```

## How It Works

### Full Pipeline Run

When you run the complete pipeline:

```bash
python main.py pipeline
```

**Behavior**: Creates a new folder with today's date (e.g., `20260127/`) and runs all 7 steps sequentially, storing all outputs in this folder.

**Example**:
```
📅 Created new run folder: 20260127
📁 All outputs will be saved to: intermediate_outputs/20260127/

--- Step 1/7: Scraping Links ---
📁 Output saved to: intermediate_outputs/20260127/01_scrape/all_links

--- Step 2/7: Deduplicating Links ---
📁 Output saved to: intermediate_outputs/20260127/02_deduplicate/link_unificati.json

... and so on
```

### Individual Step Run

When you run a single step (e.g., just scraping):

```bash
python main.py scrape
```

**Behavior**: Checks for the most recent incomplete run:

1. **If the most recent run is incomplete** (missing this step):
   - Continues that run by adding the step to the existing date folder
   - Example: If `20260127/` has steps 1-3, running step 4 will add `04_extract/` to `20260127/`

2. **If the most recent run is complete** (or no runs exist):
   - Creates a new date folder with today's date
   - Example: If all steps exist in `20260127/`, running scrape creates `20260128/01_scrape/`

**Example of Continuing an Incomplete Run**:
```bash
# Suppose 20260127/ has only 01_scrape and 02_deduplicate

python main.py classify

# Output:
📅 Using run folder: 20260127
Step 03_classify will be added to existing run folder
📁 Output saved to: intermediate_outputs/20260127/03_classify/classified_links.json
```

### Resuming a Run from a Different Day

**Scenario**: On January 1st, you run steps 1-5. On January 2nd, you want to complete step 6.

```bash
# January 1st
python main.py pipeline  # Runs steps 1-5, but step 6 fails
# Creates: intermediate_outputs/20260101/ with folders 01-05

# January 2nd
python main.py build-digests

# Output:
📅 Using run folder: 20260101
Continuing incomplete run: 20260101
Step 06_digests will be added to existing run folder
📁 Output saved to: intermediate_outputs/20260101/06_digests/email_digests_...
```

The system automatically detects that `20260101/` is incomplete (missing step 6) and continues that run instead of creating `20260102/`.

## Run Status

You can check the status of your runs using the test script:

```bash
python test_date_folders.py
```

Output shows:
```
--- Run Summary ---
Pipeline Run Summary
====================================

2026-01-27: INCOMPLETE (3/6)
  ✓ 01_scrape
  ✓ 02_deduplicate
  ✓ 03_classify
  ✗ 04_extract
  ✗ 05_match_keywords
  ✗ 06_digests

2026-01-01: COMPLETE (6/6)
  ✓ 01_scrape
  ✓ 02_deduplicate
  ✓ 03_classify
  ✓ 04_extract
  ✓ 05_match_keywords
  ✓ 06_digests
```

## Command Reference

All commands automatically use dated folders:

```bash
# Full pipeline (creates new date folder)
python main.py pipeline

# Individual steps (reuse incomplete run or create new)
python main.py scrape
python main.py deduplicate
python main.py classify
python main.py extract
python main.py match-keywords
python main.py build-digests
python main.py send-mails
```

### Custom Output Paths

You can override the automatic date folder behavior:

```bash
# Use a custom output directory (bypasses date folders)
python main.py scrape -o custom_output/

# Use a custom input file
python main.py deduplicate -i custom_input/all_links/
```

## Advanced Features

### Step Dependencies

The system validates that prerequisite steps exist before running a step:

```bash
# If you try to run step 4 without steps 1-3:
python main.py extract

# Output:
❌ Extract folder not found: intermediate_outputs/20260127/03_classify/
Please run 'python main.py classify' first
```

### Cross-Run URL Tracking

The `seen_urls.json` file (not date-stamped) tracks ALL URLs across ALL runs to prevent duplicate processing over time:

```bash
# First run
python main.py scrape
# Processes 1000 URLs

# Second run (different day)
python main.py scrape
# Processes only NEW URLs not seen in first run
```

To disable this behavior:
```bash
python main.py scrape --ignore-history
```

## Migration from Old Structure

Old structure (pre-dating):
```
intermediate_outputs/
├── 01_scrape/
│   └── all_links/
├── 02_deduplicate/
│   └── link_unificati.json
└── ...
```

New structure (with dating):
```
intermediate_outputs/
├── 20260127/
│   ├── 01_scrape/
│   ├── 02_deduplicate/
│   └── ...
├── 20260128/
│   └── ...
└── seen_urls.json
```

**Migration**: The old folders will remain untouched. New runs automatically create dated folders. You can manually move old outputs into a dated folder if needed.

## Benefits

1. **Reproducibility**: Each run's complete execution is preserved
2. **Comparison**: Easy to compare results from different runs
3. **Debugging**: Track which date produced which results
4. **Partial Runs**: Resume incomplete pipelines from any date
5. **Clean Organization**: No more mixed outputs from different runs

## Technical Details

### RunDateManager

The core logic is in `utils/run_date_manager.py`:

```python
from config import get_config

config = get_config()

# Initialize a run (determines date automatically)
run_date = config.initialize_run(
    is_full_pipeline=True,  # True for full pipeline, False for individual step
    step_name='01_scrape'   # Step name (only for individual steps)
)

# Get dated paths
scrape_folder = config.get_dated_path('01_scrape', run_date)
# Returns: intermediate_outputs/20260127/01_scrape
```

### Step Detection Logic

For individual steps, the system checks:

1. Does the most recent run folder exist?
2. Does it already contain this step? (If yes → create new date folder)
3. Does it contain all prerequisite steps? (If no → create new date folder)
4. If checks pass → continue in existing date folder

### Error Prevention

- **Missing prerequisites**: Won't run step N if step N-1 doesn't exist
- **Wrong folder writes**: Each command explicitly sets its run date
- **Validation**: Automatic checks prevent writing to wrong dated folders

## Examples

### Example 1: Full Pipeline

```bash
$ python main.py pipeline

📅 Created new run folder: 20260127
📁 All outputs will be saved to: intermediate_outputs/20260127/

--- Step 1/7: Scraping Links ---
✓ Scraped 1000 URLs
📁 intermediate_outputs/20260127/01_scrape/all_links

--- Step 2/7: Deduplicating Links ---
✓ 950 unique links
📁 intermediate_outputs/20260127/02_deduplicate/link_unificati.json

... continues through all 7 steps ...

✅ Pipeline Complete
📁 All outputs saved to: intermediate_outputs/20260127/
```

### Example 2: Continuing an Incomplete Run

```bash
# Day 1: Run steps 1-4
$ python main.py pipeline
# Fails at step 5 due to API limit

# Day 2: Continue from step 5
$ python main.py match-keywords

📅 Using run folder: 20260127
Continuing incomplete run: 20260127
Step 05_match_keywords will be added to existing run folder
✓ Matched 42 grants to recipients
📁 intermediate_outputs/20260127/05_match_keywords/grants_by_keywords_emails_...
```

### Example 3: Multiple Runs per Day

```bash
# Morning run
$ python main.py pipeline
# Creates: 20260127/ (first run today)

# Afternoon run (after config changes)
$ python main.py pipeline
# Creates: 20260127/ (reuses same folder if incomplete)
# OR creates new timestamped folder if you want separate runs
```

## Troubleshooting

### "Run date not set" Error

**Cause**: Trying to use dated paths without initializing run date

**Solution**: This should never happen with the CLI commands. If using programmatically:
```python
config.initialize_run(is_full_pipeline=False, step_name='01_scrape')
```

### Old Outputs in intermediate_outputs/

**Issue**: Old non-dated folders still exist

**Solution**: These are from before the date-stamping feature. You can:
- Leave them (they won't interfere)
- Move them into a dated folder: `mv intermediate_outputs/01_scrape intermediate_outputs/20250101/`
- Delete them if no longer needed

### Wrong Date Folder Being Used

**Check**: What folders exist?
```bash
ls intermediate_outputs/
```

**Check**: What's the most recent incomplete run?
```bash
python test_date_folders.py
```

The system always uses the most recent incomplete run, or creates a new one if all are complete.

## API Reference

See `utils/run_date_manager.py` for complete API documentation.

Key methods:
- `get_current_run_date()` - Determine which date folder to use
- `get_run_folder()` - Get path to date folder
- `get_step_folder()` - Get path to step within date folder
- `list_run_dates()` - List all existing runs
- `get_run_status()` - Check completion status of a run
- `print_run_summary()` - Display summary of all runs
