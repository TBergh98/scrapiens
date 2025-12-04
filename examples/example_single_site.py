"""
Example: Basic web scraping of a single site.

This example demonstrates how to scrape links from a single website
using the Scrapiens library.
"""

import sys
from pathlib import Path

# Add parent directory to path to import scrapiens modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import create_webdriver, scrape_site
from utils import save_links_to_file, setup_logger

# Setup logging
logger = setup_logger('example_single_site')


def main():
    """Scrape a single website and save results."""
    
    # Define site configuration
    site_config = {
        'name': 'example_research_site',
        'url': 'https://example.com/research-grants',  # Replace with actual URL
        'js': False,  # Set to True if site uses JavaScript rendering
        'next_selector': None,  # CSS selector for "next page" button if pagination exists
        'max_pages': 1  # Maximum pages to scrape
    }
    
    logger.info(f"Scraping site: {site_config['name']}")
    
    # Create web driver
    driver = create_webdriver()
    
    try:
        # Scrape the site
        links = scrape_site(driver, site_config)
        
        logger.info(f"Found {len(links)} links")
        
        # Save results
        output_file = Path('output') / f"{site_config['name']}_links.txt"
        save_links_to_file(links, output_file)
        
        logger.info(f"Results saved to {output_file}")
        
        # Print first 10 links as sample
        print("\nSample links:")
        for i, link in enumerate(sorted(links)[:10], 1):
            print(f"{i}. {link}")
        
    finally:
        driver.quit()


if __name__ == '__main__':
    main()
