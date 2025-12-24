"""Main CLI entry point for Scrapiens."""

import sys
import argparse
from pathlib import Path
from config import get_config
from utils import setup_logger, get_logger
from utils.file_utils import load_json
from scraper import (
    load_sites_from_yaml,
    load_keywords_from_yaml,
    scrape_sites,
)
from processors import deduplicate_from_directory, LinkClassifier, DigestBuilder, MailSender

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
    # Set logging level if verbose flag is set
    if hasattr(args, 'verbose') and args.verbose:
        from utils.logger import setup_logger
        setup_logger('scrapiens', level='DEBUG')
        logger.info("=== Verbose logging enabled ===")
    
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
    """Execute the classification command (classification only, no extraction)."""
    logger.info("=== Starting Link Classification ===")

    config = get_config()

    # Determine input file
    input_file = Path(args.input) if args.input else config.get_full_path('paths.unified_links_file')

    # Determine output file (default: classified_links.json)
    if args.output:
        output_file = Path(args.output)
    else:
        output_file = input_file.parent / "classified_links.json"

    # Load RSS metadata if available (from unified links file)
    rss_metadata = None
    try:
        unified_data = load_json(input_file)
        if unified_data and 'rss_metadata' in unified_data:
            rss_metadata = unified_data['rss_metadata']
            logger.info(f"Loaded RSS metadata for {len(rss_metadata)} URLs")
    except Exception as e:
        logger.debug(f"Could not load RSS metadata from input file: {e}")

    # Classify only (NO extraction)
    try:
        classifier = LinkClassifier(model=args.model)
        results = classifier.classify_from_file(
            input_file=input_file,
            output_file=output_file,
            keywords_dict=None,
            batch_size=args.batch_size,
            extract_details=False,  # Always False for classify command
            force_refresh=args.force_refresh,
            rss_metadata=rss_metadata
        )

        logger.info("=== Classification Complete ===")
        logger.info(f"Total links: {results['stats']['total_links']}")
        logger.info(f"Single grants: {results['stats']['single_grant']}")
        logger.info(f"Grant lists: {results['stats']['grant_list']}")
        logger.info(f"Other: {results['stats']['other']}")

        return 0

    except Exception as e:
        logger.error(f"Classification failed: {e}", exc_info=True)
        return 1


def cmd_extract(args):
    """Execute the extraction command (extracts details from classified grants)."""
    logger.info("=== Starting Grant Details Extraction ===")

    config = get_config()

    # Determine input file (classified_links.json from classification step)
    input_file = Path(args.input) if args.input else Path(config.get('paths.classified_links_file', 'intermediate_outputs/classified_links.json'))

    # Determine output file
    if args.output:
        output_file = Path(args.output)
    else:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Save to intermediate_outputs (not to all_links subdirectory)
        output_file = config.get_full_path('paths.classified_links_file').parent / f"extracted_grants_{timestamp}.json"

    # Load keywords for keyword matching
    try:
        _, keywords = _load_sites_and_keywords()
    except Exception as e:
        logger.error(f"Failed to load keywords: {e}")
        return 1

    # Extract grant details
    try:
        from processors import LinkClassifier
        classifier = LinkClassifier(model=args.model)
        
        # Load classifications from previous step
        if not input_file.exists():
            logger.error(f"Classification file not found: {input_file}")
            logger.info("Please run 'python main.py classify' first")
            return 1
        
        classifications_data = load_json(input_file)
        classifications = classifications_data.get('classifications', [])
        
        if not classifications:
            logger.error(f"No classifications found in {input_file}")
            return 1
        
        # Filter only single_grant URLs
        single_grant_urls = [
            c['url'] for c in classifications
            if c['category'] == 'single_grant'
        ]
        
        grant_list_count = sum(1 for c in classifications if c['category'] == 'grant_list')
        other_count = sum(1 for c in classifications if c['category'] == 'other')
        
        if grant_list_count > 0:
            logger.info(f"Skipping {grant_list_count} URLs classified as 'grant_list' (multi-grant pages)")
        if other_count > 0:
            logger.info(f"Skipping {other_count} URLs classified as 'other' (non-grant pages)")
        
        if not single_grant_urls:
            logger.warning("No single_grant URLs found to extract")
            return 1
        
        logger.info(f"Extracting details from {len(single_grant_urls)} single grant URLs")
        
        # Import and use extractor
        from processors.extractor import GrantExtractor
        from utils.cache import CacheManager
        
        cache_manager = CacheManager()
        extractor = GrantExtractor()
        
        extracted_grants = extractor.extract_batch_parallel(
            single_grant_urls,
            cache_manager=cache_manager,
            force_refresh=args.force_refresh
        )
        
        # Merge classification and extraction data
        classification_map = {c['url']: c for c in classifications}
        
        grants = []
        for grant in extracted_grants:
            url = grant['url']
            classification = classification_map.get(url, {})
            
            # Match keywords to actual content
            matched_keywords = []
            recipients = []
            
            if keywords and grant.get('extraction_success'):
                matched_keywords, recipients = classifier._match_keywords_to_content(
                    grant,
                    keywords
                )
            
            # Build grant entry
            grant_entry = {
                'url': url,
                'title': grant.get('title'),
                'organization': grant.get('organization'),
                'deadline': grant.get('deadline'),
                'funding_amount': grant.get('funding_amount'),
                'abstract': grant.get('abstract'),
                'category': classification.get('category', 'single_grant'),
                'classification_reason': classification.get('reason', ''),
                'extraction_success': grant.get('extraction_success', False),
                'extraction_date': grant.get('extraction_date'),
                'extraction_error': grant.get('error'),
                'matched_keywords': matched_keywords,
                'recipients': recipients
            }
            
            grants.append(grant_entry)
        
        # Build notifications mapping
        logger.info("Building notifications mapping")
        notifications = {}
        
        for grant in grants:
            if not grant.get('recipients'):
                continue
            
            for email in grant['recipients']:
                if email not in notifications:
                    notifications[email] = {
                        'matched_grants': [],
                        'total_grants': 0
                    }
                
                notifications[email]['matched_grants'].append({
                    'url': grant['url'],
                    'title': grant['title'],
                    'deadline': grant['deadline'],
                    'funding_amount': grant['funding_amount'],
                    'matched_keywords': grant['matched_keywords']
                })
                notifications[email]['total_grants'] += 1
        
        # Calculate statistics
        extraction_success = sum(1 for g in grants if g.get('extraction_success', False))
        stats = {
            'total_extracted': len(grants),
            'extraction_success': extraction_success,
            'total_recipients': len(notifications),
            'total_matched_grants': sum(n['total_grants'] for n in notifications.values())
        }
        
        results = {
            'grants': grants,
            'notifications': notifications,
            'stats': stats,
            'model': args.model or config.get('openai.model', 'gpt-4o-mini')
        }
        
        # Save results
        from utils.file_utils import save_json
        save_json(results, output_file)
        
        logger.info("=== Extraction Complete ===")
        logger.info(f"Extracted: {len(grants)}")
        logger.info(f"Extraction success: {extraction_success}/{len(grants)}")
        logger.info(f"Total recipients: {len(notifications)}")
        logger.info(f"Total matched grants: {stats['total_matched_grants']}")
        logger.info(f"Results saved to {output_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        return 1


def cmd_match_keywords(args):
    """Execute the keyword-to-email matching command."""
    logger.info("=== Starting Grant-Email Keyword Matching ===")
    
    from processors.grant_email_matcher import process_grants_by_keywords
    from config.settings import Config
    
    config = Config()
    
    # Determine input file (extracted grants)
    if args.input:
        grants_file = args.input
    else:
        # Find the latest extracted_grants_*.json file
        intermediate_dir = Path("intermediate_outputs")
        grants_files = list(intermediate_dir.glob("extracted_grants_*.json"))
        if not grants_files:
            logger.error("No extracted_grants_*.json files found in intermediate_outputs/")
            return 1
        grants_file = str(max(grants_files, key=lambda p: p.stat().st_mtime))
        logger.info(f"Using grants file: {grants_file}")
    
    # Keywords file (fixed path from config)
    input_dir = config.get_full_path('paths.input_dir')
    keywords_file = str(input_dir / config.get('input_files.keywords_file'))
    
    # Output file
    output_file = args.output if args.output else None
    
    # Process
    try:
        success = process_grants_by_keywords(grants_file, keywords_file, output_file, config)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Keyword matching failed: {e}", exc_info=True)
        return 1


def cmd_build_digests(args):
    """Build HTML/text digests grouped by recipient email."""
    logger.info("=== Building Email Digests ===")

    builder = DigestBuilder(template_dir=Path(args.template_dir) if args.template_dir else None)

    # Resolve source file
    if args.input:
        source_file = Path(args.input)
    else:
        try:
            source_file = builder.find_latest_source()
            logger.info(f"Using latest source file: {source_file}")
        except FileNotFoundError as e:
            logger.error(str(e))
            return 1

    output_file = Path(args.output) if args.output else None

    try:
        builder.build_digests(source_file, output_file)
        logger.info("=== Digest build complete ===")
        return 0
    except Exception as e:
        logger.error(f"Digest build failed: {e}", exc_info=True)
        return 1


def cmd_send_mails(args):
    """Send email digests to recipients and alert to admin."""
    logger.info("=== Starting Mail Send ===")

    sender = MailSender(dry_run=args.dry_run)

    # Resolve digest file
    if args.input:
        digest_file = Path(args.input)
    else:
        try:
            digest_file = sender.find_latest_digest()
            logger.info(f"Using latest digest file: {digest_file}")
        except FileNotFoundError as e:
            logger.error(str(e))
            return 1

    # Send digests
    try:
        send_summary = sender.send_digests(
            digest_file,
            mode=args.mode,
            test_recipients=None
        )
        logger.info(f"Digests sent: {send_summary['sent']}, Failed: {send_summary['failed']}")
    except Exception as e:
        logger.error(f"Digest sending failed: {e}", exc_info=True)
        return 1

    # Send alert summary unless skipped
    if not args.skip_alert:
        try:
            alert = sender.send_alert_summary(digest_file)
            if alert.get("alert_sent"):
                logger.info(f"Alert sent to {sender.alert_email}")
            else:
                logger.warning(f"Alert failed: {alert.get('alert_error')}")
        except Exception as e:
            logger.error(f"Alert sending failed: {e}", exc_info=True)

    logger.info("=== Mail send complete ===")
    return 0


def cmd_pipeline(args):
    """Execute the full pipeline."""
    # Set logging level if verbose flag is set
    if hasattr(args, 'verbose') and args.verbose:
        from utils.logger import setup_logger
        setup_logger('scrapiens', level='DEBUG')
        logger.info("=== Verbose logging enabled ===")
    
    logger.info("=== Starting Full Pipeline ===")
    
    config = get_config()
    
    # Step 1: Scrape
    logger.info("\n--- Step 1/4: Scraping Links ---")
    scrape_args = argparse.Namespace(
        problematic=args.problematic,
        output=args.scrape_output,
        save_json=True,
        verbose=getattr(args, 'verbose', False)
    )
    
    if cmd_scrape(scrape_args) != 0:
        logger.error("Pipeline failed at scraping step")
        return 1
    
    # Step 2: Deduplicate
    logger.info("\n--- Step 2/4: Deduplicating Links ---")
    dedup_args = argparse.Namespace(
        input=args.scrape_output,
        output=args.dedup_output,
        pattern="*_links.json"
    )
    
    if cmd_deduplicate(dedup_args) != 0:
        logger.error("Pipeline failed at deduplication step")
        return 1
    
    # Step 3: Classify (without extraction)
    logger.info("\n--- Step 3/4: Classifying Links ---")
    classified_file = (Path(args.dedup_output) if args.dedup_output else Path(args.scrape_output) if args.scrape_output else config.get_full_path('paths.output_dir')) / "classified_links.json"
    classify_args = argparse.Namespace(
        input=args.dedup_output,
        output=str(classified_file),
        model=args.model,
        batch_size=args.batch_size,
        force_refresh=getattr(args, 'force_refresh', False)
    )
    
    if cmd_classify(classify_args) != 0:
        logger.error("Pipeline failed at classification step")
        return 1
    
    # Step 4: Extract
    logger.info("\n--- Step 4/4: Extracting Grant Details ---")
    extract_args = argparse.Namespace(
        input=str(classified_file),
        output=args.output,
        model=args.model,
        batch_size=args.batch_size,
        force_refresh=getattr(args, 'force_refresh', False)
    )
    
    if cmd_extract(extract_args) != 0:
        logger.error("Pipeline failed at extraction step")
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
    parser_scrape.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
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
    parser_classify = subparsers.add_parser('classify', help='Classify links using OpenAI (classification only)')
    parser_classify.add_argument(
        '-i', '--input',
        help='Input JSON file (from deduplicate, default: link_unificati.json)'
    )
    parser_classify.add_argument(
        '-o', '--output',
        help='Output JSON file for classifications (default: classified_links.json)'
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
        '--force-refresh',
        action='store_true',
        help='Ignore existing results and reclassify all links'
    )
    
    # Extract command
    parser_extract = subparsers.add_parser('extract', help='Extract grant details from classified links')
    parser_extract.add_argument(
        '-i', '--input',
        help='Input JSON file with classifications (default: classified_links.json)'
    )
    parser_extract.add_argument(
        '-o', '--output',
        help='Output JSON file for extracted grants'
    )
    parser_extract.add_argument(
        '-m', '--model',
        help='OpenAI model to use (default: from config)'
    )
    parser_extract.add_argument(
        '-b', '--batch-size',
        type=int,
        default=50,
        help='Number of links per batch (default: 50)'
    )
    parser_extract.add_argument(
        '--force-refresh',
        action='store_true',
        help='Ignore cache and re-extract all grants'
    )
    
    # Match Keywords command
    parser_match = subparsers.add_parser('match-keywords', help='Match grants to emails based on keywords')
    parser_match.add_argument(
        '-i', '--input',
        help='Input JSON file with extracted grants (default: latest extracted_grants_*.json)'
    )
    parser_match.add_argument(
        '-o', '--output',
        help='Output JSON file for matched results (default: auto-generated with timestamp)'
    )

    # Build digests command
    parser_digests = subparsers.add_parser('build-digests', help='Build email digests (HTML + text) grouped by recipient')
    parser_digests.add_argument(
        '-i', '--input',
        help='Input JSON file grants_by_keywords_emails_*.json (default: latest by timestamp)'
    )
    parser_digests.add_argument(
        '-o', '--output',
        help='Output JSON file for rendered digests (default: email_digests_<timestamp>.json)'
    )
    parser_digests.add_argument(
        '--template-dir',
        help='Optional template directory override'
    )
    
    # Send mails command
    parser_send = subparsers.add_parser('send-mails', help='Send email digests to recipients and alert summary to admin')
    parser_send.add_argument(
        '-i', '--input',
        help='Input JSON file email_digests_*.json (default: latest by timestamp)'
    )
    parser_send.add_argument(
        '--mode',
        choices=['full', 'test'],
        default='full',
        help='full=send all, test=prompt for sample recipients (default: full)'
    )
    parser_send.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate sending without actual SMTP calls'
    )
    parser_send.add_argument(
        '--skip-alert',
        action='store_true',
        help='Skip sending alert summary to admin'
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
    parser_pipeline.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging - use DEBUG level if verbose flag is set for any command
    log_level = 'DEBUG' if (hasattr(args, 'verbose') and args.verbose) else 'INFO'
    setup_logger('scrapiens', level=log_level)
    
    # Execute command
    commands = {
        'scrape': cmd_scrape,
        'deduplicate': cmd_deduplicate,
        'classify': cmd_classify,
        'extract': cmd_extract,
        'match-keywords': cmd_match_keywords,
        'build-digests': cmd_build_digests,
        'send-mails': cmd_send_mails,
        'pipeline': cmd_pipeline
    }
    
    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
