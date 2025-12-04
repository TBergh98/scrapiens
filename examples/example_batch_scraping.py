"""
Example: Batch scraping multiple sites.

This example demonstrates how to scrape multiple websites from
a configuration and process them in batch.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import scrape_sites
from utils import setup_logger

# Setup logging
logger = setup_logger('example_batch_scraping')


def main():
    """Scrape multiple websites in batch."""
    
    # Define multiple sites
    sites = [
        {
            'name': 'site1',
            'url': 'https://example.com/grants',
            'js': False,
            'next_selector': None,
            'max_pages': 1
        },
        {
            'name': 'site2',
            'url': 'https://example.org/funding',
            'js': True,  # This site uses JavaScript
            'next_selector': 'button.next-page',  # Has pagination
            'max_pages': 3
        },
        {
            'name': 'site3',
            'url': 'https://example.net/calls',
            'js': False,
            'next_selector': None,
            'max_pages': 1
        }
    ]
    
    logger.info(f"Scraping {len(sites)} sites in batch")
    
    # Scrape all sites
    output_dir = Path('output') / 'batch_results'
    
    results = scrape_sites(
        sites=sites,
        output_dir=output_dir,
        save_individual=True,  # Save individual file per site
        save_combined=True  # Also save combined JSON
    )
    
    # Print summary
    print("\n=== Scraping Summary ===")
    for site_name, links in results.items():
        print(f"{site_name}: {len(links)} links")
    
    total_links = sum(len(links) for links in results.values())
    print(f"\nTotal links: {total_links}")


if __name__ == '__main__':
    main()
