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
from processors import deduplicate_from_directory, LinkClassifier
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
            'max_pages': 1,
            'keywords': ['ricerca', 'bandi']
        },
        {
            'name': 'research_site_2',
            'url': 'https://example.org/funding',
            'js': False,
            'next_selector': None,
            'max_pages': 1,
            'keywords': ['innovazione']
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
    
    dedup_file = output_dir / 'deduplicated_links.json'
    dedup_results = deduplicate_from_directory(
        input_dir=output_dir / 'scraped_links',
        output_file=dedup_file,
        file_pattern='*_links.json'
    )

    logger.info(f"Unique links: {dedup_results['stats']['unique_links']}")
    logger.info(f"Duplicates removed: {dedup_results['stats']['duplicates_removed']}")
    
    # ==========================================
    # Step 3: Classify links and extract grant details
    # ==========================================
    
    logger.info("\n=== Step 3: Classifying Links and Extracting Grant Details ===")
    
    # Note: This requires OPENAI_API_KEY to be set
    try:
        # Define keywords for matching
        keywords = {
            'mario@email.it': ['ricerca', 'innovazione'],
            'anna@email.it': ['bandi', 'grant']
        }
        
        classifier = LinkClassifier()
        
        # Classify and extract grant details
        classified_file = output_dir / 'classified_with_details.json'
        results = classifier.classify_from_file(
            input_file=dedup_file,
            output_file=classified_file,
            keywords_dict=keywords,
            batch_size=10,
            extract_details=True,
            force_refresh=False
        )
        
        logger.info(f"Classification and extraction complete:")
        logger.info(f"  Total links: {results['stats']['total_links']}")
        logger.info(f"  Single grants: {results['stats']['single_grant']}")
        logger.info(f"  Grant lists: {results['stats']['grant_list']}")
        logger.info(f"  Other: {results['stats']['other']}")
        logger.info(f"  Extracted: {results['stats']['extracted']}")
        logger.info(f"  Extraction success: {results['stats']['extraction_success']}")
        logger.info(f"  Total recipients: {results['stats']['total_recipients']}")
        logger.info(f"  Total matched grants: {results['stats']['total_matched_grants']}")
        
        # Show sample notifications
        if results['notifications']:
            logger.info("\n=== Sample Notifications ===")
            for email, notification in list(results['notifications'].items())[:2]:
                logger.info(f"\n{email}:")
                logger.info(f"  Total matched grants: {notification['total_grants']}")
                for grant in notification['matched_grants'][:2]:
                    logger.info(f"  - {grant['title']}")
                    logger.info(f"    URL: {grant['url']}")
                    logger.info(f"    Deadline: {grant['deadline']}")
                    logger.info(f"    Keywords: {grant['matched_keywords']}")
        
        # Save final results summary
        final_results = {
            'scraping_stats': {
                'total_sites': len(sites),
                'total_links_scraped': total_scraped
            },
            'deduplication_stats': dedup_results['stats'],
            'classification_stats': results['stats'],
            'notifications_count': len(results['notifications'])
        }
        
        final_file = output_dir / 'final_summary.json'
        save_json(final_results, final_file)
        
        logger.info(f"\n=== Pipeline Complete ===")
        logger.info(f"Full results saved to {classified_file}")
        logger.info(f"Summary saved to {final_file}")
        
    except Exception as e:
        logger.error(f"Classification/extraction failed: {e}", exc_info=True)
        logger.info("Make sure OPENAI_API_KEY is set in .env file")


if __name__ == '__main__':
    main()
