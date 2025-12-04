"""
Example: Complete end-to-end pipeline.

This example demonstrates the full pipeline:
1. Scrape links from multiple sites
2. Deduplicate the links
3. Classify links using OpenAI
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import scrape_sites
from processors import deduplicate_links, LinkClassifier
from utils import setup_logger, save_json

# Setup logging
logger = setup_logger('example_pipeline')


def main():
    """Run the complete scraping and classification pipeline."""
    
    output_dir = Path('output') / 'pipeline_example'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # ==========================================
    # Step 1: Scrape links from websites
    # ==========================================
    
    logger.info("=== Step 1: Scraping Links ===")
    
    sites = [
        {
            'name': 'research_site_1',
            'url': 'https://example.com/grants',
            'js': False,
            'next_selector': None,
            'max_pages': 1
        },
        {
            'name': 'research_site_2',
            'url': 'https://example.org/funding',
            'js': False,
            'next_selector': None,
            'max_pages': 1
        }
    ]
    
    scraped_results = scrape_sites(
        sites=sites,
        output_dir=output_dir / 'scraped_links',
        save_individual=True,
        save_combined=True
    )
    
    total_scraped = sum(len(links) for links in scraped_results.values())
    logger.info(f"Scraped {total_scraped} total links from {len(sites)} sites")
    
    # ==========================================
    # Step 2: Deduplicate links
    # ==========================================
    
    logger.info("\n=== Step 2: Deduplicating Links ===")
    
    dedup_results = deduplicate_links(scraped_results)
    
    logger.info(f"Unique links: {dedup_results['stats']['unique_links']}")
    logger.info(f"Duplicates removed: {dedup_results['stats']['duplicates_removed']}")
    
    # Save deduplicated links
    dedup_file = output_dir / 'deduplicated_links.json'
    save_json(dedup_results, dedup_file)
    
    # ==========================================
    # Step 3: Classify links
    # ==========================================
    
    logger.info("\n=== Step 3: Classifying Links ===")
    
    # Note: This requires OPENAI_API_KEY to be set
    try:
        classifier = LinkClassifier()
        
        classifications = classifier.classify_links(
            links=dedup_results['unique_links'][:20],  # Classify first 20 for demo
            batch_size=10
        )
        
        # Calculate statistics
        stats = {}
        for result in classifications:
            cat = result['category']
            stats[cat] = stats.get(cat, 0) + 1
        
        logger.info(f"Classification complete:")
        for category, count in stats.items():
            logger.info(f"  {category}: {count}")
        
        # Save final results
        final_results = {
            'scraping_stats': {
                'total_sites': len(sites),
                'total_links_scraped': total_scraped
            },
            'deduplication_stats': dedup_results['stats'],
            'classification_stats': stats,
            'classifications': classifications
        }
        
        final_file = output_dir / 'final_results.json'
        save_json(final_results, final_file)
        
        logger.info(f"\n=== Pipeline Complete ===")
        logger.info(f"Final results saved to {final_file}")
        
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        logger.info("Make sure OPENAI_API_KEY is set in .env file")


if __name__ == '__main__':
    main()
