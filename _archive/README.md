# Archived Documentation

This folder contains deprecated and development documentation that has been archived from the main workspace.

## Contents

### `/docs/` - Implementation Details (Archived)
- **DATE_STAMPED_FOLDERS.md** - User guide for date-stamped folder structure (covered in main README)
- **DATE_STAMPED_IMPLEMENTATION.md** - Low-level implementation details (feature is now stable)
- **PREPROCESSING_IMPLEMENTATION.md** - EC Europa preprocessing algorithm details (not user-facing)
- **KEYWORD_MATCHING.md** - Match-keywords command guide (covered by CLI help and README)

### `/scripts/` - Development & Testing Scripts
- **test_date_folders.py** - Comprehensive test of RunDateManager (useful as reference but not part of pytest suite)

## Why These Were Archived

1. **Implementation Details**: Once a feature is stable and documented in the main README, the detailed implementation docs become technical debt. These are kept for reference but removed from the active workspace.

2. **Duplicate Documentation**: Information already covered in `README.md` or accessible via `--help` flags doesn't need separate documentation files.

3. **Development Artifacts**: Scripts used during development that aren't part of the automated test suite are archived rather than deleted, preserving them for reference.

## Using Archived Files

If you need to reference any of these files:
- Check the main README first (most documentation is there)
- Review CLI help: `python main.py <command> --help`
- Consult the active docs in `../docs/`
- Reference these archived files only if additional context is needed

## When to Move Files Back

Move a file back to the main workspace if:
- The feature is being actively developed again
- Implementation details become necessary for debugging/modification
- Documentation needs to be refreshed based on these details

---

Archived: 2026-01-27
Cleanup Reason: Workspace organization - removing deprecated/duplicate documentation and consolidating implementation reports
