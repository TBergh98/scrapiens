# Date-Stamped Folders Implementation Summary

## Changes Made

### 1. New Utility Module: `utils/run_date_manager.py`

Created `RunDateManager` class that handles:
- Determining appropriate run date for full pipeline vs individual steps
- Creating and managing date-stamped output folders (e.g., `intermediate_outputs/20260127/`)
- Detecting incomplete runs and allowing continuation
- Validating step dependencies
- Listing and reporting on existing runs

Key features:
- Full pipeline always creates new date folder
- Individual steps reuse most recent incomplete run or create new date folder
- Prevents writing to wrong dated folders
- Validates prerequisite steps exist

### 2. Enhanced Config: `config/settings.py`

Added to `Config` class:
- `run_date_manager` property - lazy-initialized RunDateManager instance
- `set_run_date(run_date)` - set current session run date
- `get_run_date()` - get current session run date
- `get_dated_path(step_name, run_date)` - get path to dated step folder
- `ensure_dated_folder(step_name, run_date)` - create dated folder if needed
- `initialize_run(is_full_pipeline, step_name)` - determine and set run date

### 3. Updated CLI Commands: `main.py`

All 7 commands now use date-stamped folders:

**cmd_scrape**:
- Initializes run date with `initialize_run(is_full_pipeline=False, step_name='01_scrape')`
- Creates/uses `intermediate_outputs/YYYYMMDD/01_scrape/all_links/`
- Creates/uses `intermediate_outputs/YYYYMMDD/01_scrape/rss_feeds/`

**cmd_deduplicate**:
- Initializes run date for step '02_deduplicate'
- Reads from dated `01_scrape/all_links/` folder
- Writes to dated `02_deduplicate/link_unificati.json`

**cmd_classify**:
- Initializes run date for step '03_classify'
- Reads from dated `02_deduplicate/link_unificati.json`
- Writes to dated `03_classify/classified_links.json`

**cmd_extract**:
- Initializes run date for step '04_extract'
- Reads from dated `03_classify/classified_links.json`
- Writes to dated `04_extract/extracted_grants_*.json`

**cmd_match_keywords**:
- Initializes run date for step '05_match_keywords'
- Reads from dated `04_extract/extracted_grants_*.json`
- Writes to dated `05_match_keywords/grants_by_keywords_emails_*.json`

**cmd_build_digests**:
- Initializes run date for step '06_digests'
- Reads from dated `05_match_keywords/grants_by_keywords_emails_*.json`
- Writes to dated `06_digests/email_digests_*.json`

**cmd_send_mails**:
- Searches for most recent `06_digests/email_digests_*.json` across all run dates
- No initialization needed (reads only)

**cmd_pipeline**:
- Initializes with `initialize_run(is_full_pipeline=True)` - always creates new date folder
- Executes all 7 steps in sequence within the same dated folder
- Explicit path passing ensures all steps use the same run date

### 4. Updated Scraper: `scraper/link_extractor.py`

**scrape_sites** function:
- Added optional `rss_dir` parameter
- If not provided, uses config default (backward compatible)
- Allows main.py to specify dated RSS folder

### 5. Updated Deduplicator: `processors/deduplicator.py`

**deduplicate_from_directory** function:
- Added optional `rss_dir` parameter
- Smart RSS folder detection:
  - If `rss_dir` provided, uses it
  - Else tries `input_dir/../rss_feeds` (same dated run)
  - Else falls back to config default
- Automatically finds RSS metadata in same dated run

### 6. Updated Utils: `utils/__init__.py`

- Exported `RunDateManager` class

## Backward Compatibility

- Old non-dated folders in `intermediate_outputs/` are left untouched
- Config still has old paths for backward compatibility
- Individual processor functions accept explicit paths (works with or without dating)
- Custom output paths via CLI args still work (`-o custom_output/`)

## Testing

Created `test_date_folders.py` to verify:
- Run date determination logic
- Folder creation
- Config integration
- Incomplete run detection
- Path resolution

All tests pass successfully.

## Documentation

Created comprehensive documentation:
- `docs/DATE_STAMPED_FOLDERS.md` - Complete user guide
- Updated `README.md` with new feature highlights
- Inline code documentation

## Benefits

1. **Reproducibility**: All outputs from a single run stay together
2. **Organization**: Easy to track multiple runs over time
3. **Partial Run Support**: Resume incomplete pipelines from any date
4. **Error Prevention**: Validates dependencies and prevents wrong folder writes
5. **Clean Separation**: No more mixed outputs from different runs
6. **Debugging**: Clear which date produced which results

## Example Usage

### Full Pipeline (New Run)
```bash
python main.py pipeline
# Creates: intermediate_outputs/20260127/ with all 6 step folders
```

### Continuing Incomplete Run
```bash
# Day 1: Run steps 1-4
python main.py pipeline  # Fails at step 5

# Day 2: Continue from step 5
python main.py match-keywords
# Detects incomplete 20260127/ and adds step 5 there
```

### Individual Steps
```bash
python main.py scrape
# If most recent run incomplete and missing scrape: adds to that run
# Otherwise: creates new dated folder

python main.py deduplicate
# Automatically finds scrape output in same dated run
```

## File Structure

### Before (Old)
```
intermediate_outputs/
├── 01_scrape/
│   └── all_links/
├── 02_deduplicate/
│   └── link_unificati.json
└── ...
```

### After (New)
```
intermediate_outputs/
├── 20260101/
│   ├── 01_scrape/
│   │   ├── all_links/
│   │   └── rss_feeds/
│   ├── 02_deduplicate/
│   │   └── link_unificati.json
│   ├── 03_classify/
│   ├── 04_extract/
│   ├── 05_match_keywords/
│   └── 06_digests/
├── 20260127/
│   └── ...
└── seen_urls.json  # Cross-run tracking (not dated)
```

## Edge Cases Handled

1. **Missing prerequisites**: Won't run step N if step N-1 doesn't exist in same run
2. **Multiple incomplete runs**: Always uses most recent incomplete run
3. **Same-day reruns**: Continues existing date folder if incomplete
4. **Cross-day continuation**: Resumes old date folder if it's the most recent incomplete
5. **Custom paths**: CLI overrides bypass dating system when needed

## Code Quality

- Type hints throughout
- Comprehensive logging with emoji indicators
- Error handling and validation
- Clean separation of concerns
- No breaking changes to existing APIs

## Migration Path

No migration needed. New runs automatically use dated folders. Old outputs can remain in place or be manually organized into dated folders if desired.
