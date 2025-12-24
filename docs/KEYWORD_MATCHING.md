## Grant-Email Keyword Matcher

### Overview

The `grant_email_matcher` module matches extracted grants against keywords from `keywords.yaml` and associates each grant with the emails whose keywords were found in the grant's description or title.

**Key Features:**
- Case-insensitive word-boundary keyword matching
- High performance: ~0.3 seconds for 1500+ grants
- Pre-compiled regex patterns for speed
- Inverted keyword index for O(1) lookup

### How It Works

1. **Load Keywords**: Reads `input/keywords.yaml` which maps emails to their keywords
2. **Load Grants**: Reads `extracted_grants_*.json` file from `intermediate_outputs/`
3. **Match Process**:
   - For each grant, extract searchable text (priority: `abstract` → `title`)
   - Quickly find all keywords that match in the text (using substring pre-filter + regex)
   - Map matched keywords to their associated emails
4. **Output**: Saves to `intermediate_outputs/grants_by_keywords_emails_TIMESTAMP.json`

### Usage

#### CLI Command

```bash
# Auto-detect latest extracted_grants_*.json and use keywords.yaml from input/
python main.py match-keywords

# Specify input and output files
python main.py match-keywords -i intermediate_outputs/extracted_grants_20251211_162451.json -o results.json

# Use custom output path
python main.py match-keywords -o my_output.json
```

#### Python API

```python
from processors.grant_email_matcher import GrantEmailMatcher
from config.settings import Config

# Initialize
config = Config()
matcher = GrantEmailMatcher(config)

# Process
success = matcher.process(
    grants_file="intermediate_outputs/extracted_grants_20251211_162451.json",
    keywords_file="input/keywords.yaml",
    output_file="results.json"  # Optional, auto-generated if None
)

if success:
    print("Matching complete!")
```

Or use the standalone function:

```python
from processors.grant_email_matcher import process_grants_by_keywords

success = process_grants_by_keywords(
    grants_file="...",
    keywords_file="...",
    output_file="..."
)
```

### Output Format

The output JSON contains:

```json
{
  "processing_date": "2025-12-19T16:55:03.749394",
  "grants_file": "intermediate_outputs/extracted_grants_20251211_162451.json",
  "keywords_file": "input/keywords.yaml",
  "total_grants": 1480,
  "grants_with_keyword_matches": 306,
  "match_rate": 20.68,
  "total_emails": 39,
  "results": [
    {
      "grant_index": 7,
      "url": "https://example.com/grant",
      "title": "Grant Title",
      "organization": "Organization Name",
      "abstract": "Grant description...",
      "deadline": "2025-12-31",
      "funding_amount": "€100,000",
      "extraction_date": "2025-12-11T14:47:03.140186",
      "matched_emails": [
        {
          "email": "user1@example.com",
          "matched_keywords": ["keyword1", "keyword2"]
        },
        {
          "email": "user2@example.com",
          "matched_keywords": ["keyword3"]
        }
      ]
    }
  ]
}
```

### Performance Notes

- **Optimization 1**: Pre-filter keywords with substring match before regex (much faster)
- **Optimization 2**: Pre-compile all regex patterns once during initialization
- **Optimization 3**: Inverted index: keyword → emails (O(1) lookup)
- **Result**: 1480 grants matched in ~0.3 seconds

### Example

See [examples/example_keyword_matching.py](../examples/example_keyword_matching.py) for:
- Basic usage example
- Custom output path example
- Results analysis example with statistics by email

Run it:
```bash
python examples/example_keyword_matching.py
```

### Integration with Pipeline

The matcher works with extracted grant data from the main pipeline:

```
scrape → deduplicate → classify → extract → [match-keywords] ← keywords.yaml
```

After running extraction, use:
```bash
python main.py extract -o extracted_grants.json
python main.py match-keywords  # Uses extracted_grants.json automatically
```

### Notes

- **Text Priority**: Searches both `abstract` and `title`. If both are empty/null, grant is skipped.
- **Case Insensitive**: All matching is case-insensitive using regex flags.
- **Word Boundaries**: Keywords must match whole words (e.g., "animal" matches "animal health" but not "animals").
- **Multiple Matches**: Each email associated with a grant appears once with a list of all matched keywords.
