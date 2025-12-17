"""
Example: RSS-based scraping.

Demonstrates how to configure and use RSS feeds for faster scraping.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import scrape_sites
from utils import setup_logger

logger = setup_logger('example_rss_scraping')


def main():
    """Scrape sites using RSS feeds."""
    
    sites = [
        {
            'name': 'nature_grants',
            'url': 'https://www.nature.com',
            'rss_url': 'https://www.nature.com/nature.rss',  # RSS enabled
            'js': False,
            'next_selector': None,
            'max_pages': 1,
            'pagination_param': None
        },
        {
            'name': 'standard_site',
            'url': 'https://example.com/grants',
            'rss_url': None,  # No RSS - will use Selenium/HTTP
            'js': False,
            'next_selector': None,
            'max_pages': 1,
            'pagination_param': None
        }
    ]
    
    output_dir = Path('output') / 'rss_example'
    
    results = scrape_sites(
        sites=sites,
        output_dir=output_dir,
        save_individual=True
    )
    
    for site_name, links in results.items():
        logger.info(f"{site_name}: {len(links)} links scraped")


if __name__ == '__main__':
    main()
