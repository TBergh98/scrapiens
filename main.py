"""Main CLI entry point for Scrapiens."""

import sys
import argparse
from pathlib import Path
from config import get_config
from utils import setup_logger, get_logger
from scraper import (
    load_sites_from_yaml,
    load_keywords_from_yaml,
    scrape_sites,
)
from processors import deduplicate_from_directory, LinkClassifier

# Setup logger
logger = get_logger(__name__)


def _load_sites_and_keywords():
    """Helper to load sites and keywords from YAML files defined in config."""
    config = get_config()
    input_dir = config.get_full_path('paths.input_dir')

    sites_path = input_dir / config.get('input_files.sites_file')
    keywords_path = input_dir / config.get('input_files.keywords_file')

    sites = load_sites_from_yaml(sites_path)
    keywords = load_keywords_from_yaml(keywords_path)

    return sites, keywords


def cmd_scrape(args):
    """Execute the scraping command."""
    logger.info("=== Starting Link Scraping ===")

    # Load sites (keywords are loaded later in pipeline/classify)
    try:
        sites, _ = _load_sites_and_keywords()
    except Exception as e:
        logger.error(f"Failed to load sites: {e}")
        return 1

    if not sites:
        logger.error("No sites loaded from YAML configuration")
        return 1

    config = get_config()

    # Determine output directory
    output_dir = Path(args.output) if args.output else config.get_full_path('paths.output_dir')

    # Scrape sites
    try:
        results = scrape_sites(
            sites=sites,
            output_dir=output_dir,
            save_individual=True,
            save_combined=args.save_json
        )

        logger.info(f"=== Scraping Complete: {len(results)} sites processed ===")
        return 0

    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        return 1


def cmd_deduplicate(args):
    """Execute the deduplication command."""
    logger.info("=== Starting Link Deduplication ===")
    
    config = get_config()
    
    # Determine input directory
    if args.input:
        input_dir = Path(args.input)
    else:
        input_dir = config.get_full_path('paths.output_dir')
    
    # Determine output file
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = config.get_full_path('paths.unified_links_file')
    
    # Deduplicate
    try:
        results = deduplicate_from_directory(
            input_dir=input_dir,
            output_file=output_file,
            file_pattern=args.pattern
        )
        
        logger.info("=== Deduplication Complete ===")
        logger.info(f"Unique links: {results['stats']['unique_links']}")
        logger.info(f"Duplicates removed: {results['stats']['duplicates_removed']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Deduplication failed: {e}", exc_info=True)
        return 1


def cmd_classify(args):
    """Execute the classification command."""
    logger.info("=== Starting Link Classification ===")

    config = get_config()

    # Determine input file
    input_file = Path(args.input) if args.input else config.get_full_path('paths.unified_links_file')

    # Determine output file
    output_file = Path(args.output) if args.output else input_file.parent / f"{input_file.stem}_classified.json"

    # Load keywords
    try:
        _, keywords = _load_sites_and_keywords()
    except Exception as e:
        logger.error(f"Failed to load keywords: {e}")
        return 1

    # Classify and extract
    try:
        classifier = LinkClassifier(model=args.model)
        results = classifier.classify_from_file(
            input_file=input_file,
            output_file=output_file,
            keywords_dict=keywords,
            batch_size=args.batch_size,
            extract_details=args.extract_details,
            force_refresh=args.force_refresh
        )

        logger.info("=== Classification Complete ===")
        logger.info(f"Total links: {results['stats']['total_links']}")
        logger.info(f"Single grants: {results['stats']['single_grant']}")
        logger.info(f"Grant lists: {results['stats']['grant_list']}")
        logger.info(f"Other: {results['stats']['other']}")
        
        if args.extract_details:
            logger.info(f"Extracted: {results['stats']['extracted']}")
            logger.info(f"Extraction success: {results['stats']['extraction_success']}")
            logger.info(f"Total recipients: {results['stats']['total_recipients']}")
            logger.info(f"Total matched grants: {results['stats']['total_matched_grants']}")
        
        logger.info(f"Average confidence: {results['stats']['avg_confidence']}")

        return 0

    except Exception as e:
        logger.error(f"Classification failed: {e}", exc_info=True)
        return 1


def cmd_pipeline(args):
    """Execute the full pipeline."""
    logger.info("=== Starting Full Pipeline ===")
    
    # Step 1: Scrape
    logger.info("\n--- Step 1/3: Scraping Links ---")
    scrape_args = argparse.Namespace(
        problematic=args.problematic,
        output=args.scrape_output,
        save_json=True
    )
    
    if cmd_scrape(scrape_args) != 0:
        logger.error("Pipeline failed at scraping step")
        return 1
    
    # Step 2: Deduplicate
    logger.info("\n--- Step 2/3: Deduplicating Links ---")
    dedup_args = argparse.Namespace(
        input=args.scrape_output,
        output=args.dedup_output,
        pattern="*_links.json"
    )
    
    if cmd_deduplicate(dedup_args) != 0:
        logger.error("Pipeline failed at deduplication step")
        return 1
    
    # Step 3: Classify and Extract
    logger.info("\n--- Step 3/3: Classifying Links and Extracting Grant Details ---")
    classify_args = argparse.Namespace(
        input=args.dedup_output,
        output=args.output,
        model=args.model,
        batch_size=args.batch_size,
        extract_details=True,
        force_refresh=getattr(args, 'force_refresh', False)
    )
    
    # Inject keywords into classify step
    if cmd_classify(classify_args) != 0:
        logger.error("Pipeline failed at classification step")
        return 1
    
    logger.info("\n=== Pipeline Complete ===")
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scrapiens - Research Grant Link Scraper and Classifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape standard sites
  python main.py scrape
  
  # Scrape problematic sites
  python main.py scrape --problematic
  
  # Deduplicate links
  python main.py deduplicate
  
  # Classify links
  python main.py classify
  
  # Run full pipeline
  python main.py pipeline
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Scrape command
    parser_scrape = subparsers.add_parser('scrape', help='Scrape links from websites')
    parser_scrape.add_argument(
        '--problematic',
        action='store_true',
        help='Scrape problematic sites instead of standard sites'
    )
    parser_scrape.add_argument(
        '-o', '--output',
        help='Output directory for scraped links'
    )
    parser_scrape.add_argument(
        '--save-json',
        action='store_true',
        help='Save combined JSON file'
    )
    
    # Deduplicate command
    parser_dedup = subparsers.add_parser('deduplicate', help='Deduplicate scraped links')
    parser_dedup.add_argument(
        '-i', '--input',
        help='Input directory containing link files'
    )
    parser_dedup.add_argument(
        '-o', '--output',
        help='Output JSON file for deduplicated links'
    )
    parser_dedup.add_argument(
        '-p', '--pattern',
        default='*_links.json',
        help='File pattern to match (default: *_links.json)'
    )
    
    # Classify command
    parser_classify = subparsers.add_parser('classify', help='Classify links using OpenAI')
    parser_classify.add_argument(
        '-i', '--input',
        help='Input JSON file (from deduplicate)'
    )
    parser_classify.add_argument(
        '-o', '--output',
        help='Output JSON file for classifications'
    )
    parser_classify.add_argument(
        '-m', '--model',
        help='OpenAI model to use (default: from config)'
    )
    parser_classify.add_argument(
        '-b', '--batch-size',
        type=int,
        default=50,
        help='Number of links per batch (default: 50)'
    )
    parser_classify.add_argument(
        '--no-extract',
        dest='extract_details',
        action='store_false',
        default=True,
        help='Skip grant details extraction (classify only)'
    )
    parser_classify.add_argument(
        '--force-refresh',
        action='store_true',
        help='Ignore cache and re-extract all grants'
    )
    
    # Pipeline command
    parser_pipeline = subparsers.add_parser('pipeline', help='Run full pipeline')
    parser_pipeline.add_argument(
        '--problematic',
        action='store_true',
        help='Process problematic sites instead of standard sites'
    )
    parser_pipeline.add_argument(
        '--scrape-output',
        help='Output directory for scraping step'
    )
    parser_pipeline.add_argument(
        '--dedup-output',
        help='Output file for deduplication step'
    )
    parser_pipeline.add_argument(
        '-o', '--output',
        help='Final output file for classified links'
    )
    parser_pipeline.add_argument(
        '-m', '--model',
        help='OpenAI model to use (default: from config)'
    )
    parser_pipeline.add_argument(
        '-b', '--batch-size',
        type=int,
        default=50,
        help='Number of links per batch (default: 50)'
    )
    parser_pipeline.add_argument(
        '--force-refresh',
        action='store_true',
        help='Ignore cache and re-extract all grants'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    setup_logger('scrapiens')
    
    # Execute command
    commands = {
        'scrape': cmd_scrape,
        'deduplicate': cmd_deduplicate,
        'classify': cmd_classify,
        'pipeline': cmd_pipeline
    }
    
    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
