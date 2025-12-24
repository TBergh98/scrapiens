"""
Example: Using the Grant-Email Keyword Matcher

This example demonstrates how to use the GrantEmailMatcher module to match grants
against keywords and associate them with email addresses.

Usage:
    python examples/example_keyword_matching.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from processors.grant_email_matcher import GrantEmailMatcher, process_grants_by_keywords
from config.settings import Config
from utils.file_utils import load_json
from utils.logger import get_logger

logger = get_logger(__name__)


def find_latest_grants_file(base_dir: str = "intermediate_outputs") -> str:
    """Find the most recent extracted_grants_*.json file."""
    grants_files = list(Path(base_dir).glob("extracted_grants_*.json"))
    
    if not grants_files:
        raise FileNotFoundError(f"No extracted_grants_*.json files found in {base_dir}")
    
    # Sort by modification time, get latest
    latest = max(grants_files, key=lambda p: p.stat().st_mtime)
    logger.info(f"Using grants file: {latest.name}")
    return str(latest)


def example_basic_usage():
    """Example 1: Basic usage of GrantEmailMatcher."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Keyword Matching")
    print("="*70)
    
    config = Config()
    matcher = GrantEmailMatcher(config)
    
    # Paths
    grants_file = find_latest_grants_file()
    keywords_file = "input/keywords.yaml"
    
    # Process
    success = matcher.process(grants_file, keywords_file)
    
    if success:
        print("\n✓ Processing completed successfully!")
    else:
        print("\n✗ Processing failed!")


def example_custom_output():
    """Example 2: Custom output file path."""
    print("\n" + "="*70)
    print("EXAMPLE 2: Custom Output File")
    print("="*70)
    
    grants_file = find_latest_grants_file()
    keywords_file = "input/keywords.yaml"
    output_file = "intermediate_outputs/custom_keyword_matches.json"
    
    # Use standalone function with custom output
    success = process_grants_by_keywords(grants_file, keywords_file, output_file)
    
    if success:
        print(f"\n✓ Results saved to: {output_file}")
    else:
        print("\n✗ Processing failed!")


def example_analyze_results():
    """Example 3: Analyze the matching results."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Analyzing Matching Results")
    print("="*70)
    
    # Run matching first
    grants_file = find_latest_grants_file()
    keywords_file = "input/keywords.yaml"
    
    matcher = GrantEmailMatcher()
    if not matcher.process(grants_file, keywords_file):
        print("✗ Processing failed!")
        return
    
    # Load the results to analyze
    results_files = list(Path("intermediate_outputs").glob("grants_by_keywords_emails_*.json"))
    if not results_files:
        print("No results files found!")
        return
    
    latest_results = max(results_files, key=lambda p: p.stat().st_mtime)
    data = load_json(latest_results)
    
    print(f"\nResults from: {latest_results.name}")
    print(f"Total grants analyzed: {data['total_grants']}")
    print(f"Grants with matches: {data['grants_with_keyword_matches']} ({data['match_rate']}%)")
    print(f"Emails tracked: {data['total_emails']}")
    
    # Analyze email statistics
    print("\n" + "-"*70)
    print("MATCHES BY EMAIL:")
    print("-"*70)
    
    email_stats = {}
    for result in data['results']:
        for email_match in result['matched_emails']:
            email = email_match['email']
            if email not in email_stats:
                email_stats[email] = {
                    'grants_found': 0,
                    'total_keywords_matched': 0,
                    'unique_keywords': set()
                }
            email_stats[email]['grants_found'] += 1
            email_stats[email]['total_keywords_matched'] += len(email_match['matched_keywords'])
            email_stats[email]['unique_keywords'].update(email_match['matched_keywords'])
    
    # Sort by grants found
    for email in sorted(email_stats.keys(), key=lambda e: email_stats[e]['grants_found'], reverse=True):
        stats = email_stats[email]
        print(f"\n{email}")
        print(f"  Grants found: {stats['grants_found']}")
        print(f"  Total keyword matches: {stats['total_keywords_matched']}")
        print(f"  Unique keywords matched: {len(stats['unique_keywords'])}")
        print(f"  Top keywords: {', '.join(sorted(stats['unique_keywords'])[:5])}...")
    
    # Show sample grants
    print("\n" + "-"*70)
    print("SAMPLE MATCHED GRANTS (first 3):")
    print("-"*70)
    
    for grant in data['results'][:3]:
        print(f"\nTitle: {grant['title']}")
        print(f"URL: {grant['url']}")
        print(f"Matched for:")
        for email_match in grant['matched_emails']:
            print(f"  • {email_match['email']}: {', '.join(email_match['matched_keywords'][:3])}...")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("GRANT EMAIL KEYWORD MATCHER - EXAMPLES")
    print("="*70)
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    try:
        # Example 1: Basic usage
        example_basic_usage()
        
        # Example 2: Custom output
        example_custom_output()
        
        # Example 3: Analyze results
        example_analyze_results()
        
        print("\n" + "="*70)
        print("ALL EXAMPLES COMPLETED")
        print("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    main()
