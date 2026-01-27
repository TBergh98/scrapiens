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
    
    # Ask user if they want to ignore history (unless --ignore-history flag is set)
    ignore_history = getattr(args, 'ignore_history', False)
    if not ignore_history:
        try:
            response = input("\n❓ Includere bandi delle run precedenti? (y/N): ").strip().lower()
            ignore_history = response in ['y', 'yes', 's', 'si', 'sì']
            if ignore_history:
                logger.info("✅ Includerò anche i bandi delle run precedenti")
            else:
                logger.info("✅ Filtrerò i bandi già visti nelle run precedenti (comportamento di default)")
        except (EOFError, KeyboardInterrupt):
            logger.info("\n⏭️  Nessuna risposta: uso comportamento di default (NON includere bandi precedenti)")
            ignore_history = False

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
    
    # Initialize run date (01_scrape)
    run_date = config.initialize_run(is_full_pipeline=False, step_name='01_scrape')
    logger.info(f"[Date] Using run folder: {run_date}")

    # Determine output directory (use dated folder)
    if args.output:
        output_dir = Path(args.output)
        rss_dir = None  # Let scraper use default
    else:
        scrape_folder = config.ensure_dated_folder('01_scrape', run_date)
        output_dir = scrape_folder / 'all_links'
        rss_dir = scrape_folder / 'rss_feeds'

    # Scrape sites
    try:
        results = scrape_sites(
            sites=sites,
            output_dir=output_dir,
            save_individual=True,
            save_combined=args.save_json,
            ignore_history=ignore_history,
            rss_dir=rss_dir
        )

        logger.info(f"=== Scraping Complete: {len(results)} sites processed ===")
        logger.info(f"[Output] saved to: {output_dir}")
        return 0

    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        return 1


def cmd_deduplicate(args):
    """Execute the deduplication command."""
    logger.info("=== Starting Link Deduplication ===")
    
    config = get_config()
    
    # Initialize run date (02_deduplicate)
    run_date = config.initialize_run(is_full_pipeline=False, step_name='02_deduplicate')
    logger.info(f"[Date] Using run folder: {run_date}")
    
    # Determine input directory (should be from 01_scrape of same run)
    if args.input:
        input_dir = Path(args.input)
    else:
        scrape_folder = config.get_dated_path('01_scrape', run_date)
        input_dir = scrape_folder / 'all_links'
        if not input_dir.exists():
            logger.error(f"Scrape folder not found: {input_dir}")
            logger.error("Please run 'python main.py scrape' first")
            return 1
    
    # Determine output file (in 02_deduplicate of same run)
    if args.output:
        output_file = Path(args.output)
    else:
        dedup_folder = config.ensure_dated_folder('02_deduplicate', run_date)
        output_file = dedup_folder / "link_unificati.json"
    
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
        logger.info(f"[Output] saved to: {output_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Deduplication failed: {e}", exc_info=True)
        return 1


def cmd_classify(args):
    """Execute the classification command (classification only, no extraction)."""
    logger.info("=== Starting Link Classification ===")

    config = get_config()
    
    # Initialize run date (03_classify)
    run_date = config.initialize_run(is_full_pipeline=False, step_name='03_classify')
    logger.info(f"[Date] Using run folder: {run_date}")

    # Determine input file (should be from 02_deduplicate of same run)
    if args.input:
        input_file = Path(args.input)
    else:
        dedup_folder = config.get_dated_path('02_deduplicate', run_date)
        input_file = dedup_folder / "link_unificati.json"
        if not input_file.exists():
            logger.error(f"Deduplicated links file not found: {input_file}")
            logger.error("Please run 'python main.py deduplicate' first")
            return 1

    # Determine output file (in 03_classify of same run)
    if args.output:
        output_file = Path(args.output)
    else:
        classify_folder = config.ensure_dated_folder('03_classify', run_date)
        output_file = classify_folder / "classified_links.json"

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
        logger.info(f"[Output] Output saved to: {output_file}")

        return 0

    except Exception as e:
        logger.error(f"Classification failed: {e}", exc_info=True)
        return 1


def cmd_extract(args):
    """Execute the extraction command (extracts details from classified grants)."""
    logger.info("=== Starting Grant Details Extraction ===")

    config = get_config()
    
    # Initialize run date (04_extract)
    run_date = config.initialize_run(is_full_pipeline=False, step_name='04_extract')
    logger.info(f"[Date] Using run folder: {run_date}")

    # Determine input file (should be from 03_classify of same run)
    if args.input:
        input_file = Path(args.input)
    else:
        classify_folder = config.get_dated_path('03_classify', run_date)
        input_file = classify_folder / "classified_links.json"
        if not input_file.exists():
            logger.error(f"Classification file not found: {input_file}")
            logger.error("Please run 'python main.py classify' first")
            return 1

    # Determine output file (in 04_extract of same run)
    if args.output:
        output_file = Path(args.output)
    else:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        extract_folder = config.ensure_dated_folder('04_extract', run_date)
        output_file = extract_folder / f"extracted_grants_{timestamp}.json"

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
        extractor = GrantExtractor(model=args.model)
        
        # Prepare classification map
        classification_map = {c['url']: c for c in classifications}
        
        # Extract grants with incremental saving
        extracted_grants = extractor.extract_batch_parallel(
            single_grant_urls,
            cache_manager=cache_manager,
            force_refresh=args.force_refresh,
            output_file=output_file,
            classifications=classification_map,
            keywords=keywords,
            keyword_classifier=classifier
        )
        
        # Load saved results to display final stats
        results_data = load_json(output_file)
        
        logger.info("=== Extraction Complete ===")
        logger.info(f"Extracted: {len(extracted_grants)}")
        logger.info(f"Extraction success: {results_data['stats']['extraction_success']}/{len(extracted_grants)}")
        logger.info(f"Total recipients: {results_data['stats']['total_recipients']}")
        logger.info(f"Total matched grants: {results_data['stats']['total_matched_grants']}")
        logger.info(f"[Output] Results saved to {output_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        return 1


def cmd_match_keywords(args):
    """Execute the keyword-to-email matching command."""
    logger.info("=== Starting Grant-Email Keyword Matching ===")
    
    from processors.grant_email_matcher import process_grants_by_keywords
    from utils.sent_grants_manager import SentGrantsManager
    from config.settings import Config
    
    config = Config()
    
    # Initialize run date (05_match_keywords)
    run_date = config.initialize_run(is_full_pipeline=False, step_name='05_match_keywords')
    logger.info(f"[05_match_keywords] Using run folder: {run_date}")
    
    # Determine input file (extracted grants from 04_extract of same run)
    if args.input:
        grants_file = args.input
    else:
        # Find the latest extracted_grants_*.json file in the run's 04_extract folder
        extract_folder = config.get_dated_path('04_extract', run_date)
        if not extract_folder.exists():
            logger.error(f"Extract folder not found: {extract_folder}")
            logger.error("Please run 'python main.py extract' first")
            return 1
            
        grants_files = list(extract_folder.glob("extracted_grants_*.json"))
        if not grants_files:
            logger.error(f"No extracted_grants_*.json files found in {extract_folder}")
            return 1
        grants_file = str(max(grants_files, key=lambda p: p.stat().st_mtime))
        logger.info(f"Using grants file: {grants_file}")
    
    # Keywords file (fixed path from config)
    input_dir = config.get_full_path('paths.input_dir')
    keywords_file = str(input_dir / config.get('input_files.keywords_file'))
    
    # Output file (in 05_match_keywords of same run)
    if args.output:
        output_file = args.output
    else:
        match_folder = config.ensure_dated_folder('05_match_keywords', run_date)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = str(match_folder / f"grants_by_keywords_emails_{timestamp}.json")
    
    # Create sent grants manager
    sent_manager = SentGrantsManager()
    
    # Determine filtering behavior based on arguments
    exclude_already_sent = not args.include_sent  # Default: True, exclude previously sent
    exclude_failed_extraction = not args.retry_failed  # Default: True, exclude failed
    exclude_expired_deadline = not args.include_expired  # Default: True, exclude expired
    
    logger.info(
        f"Filtering settings:\n"
        f"  - Exclude already sent: {exclude_already_sent}\n"
        f"  - Exclude failed extraction: {exclude_failed_extraction}\n"
        f"  - Exclude expired deadline: {exclude_expired_deadline}"
    )
    
    # Process
    try:
        success, output_data = process_grants_by_keywords(
            grants_file,
            keywords_file,
            output_file,
            config,
            exclude_already_sent=exclude_already_sent,
            exclude_failed_extraction=exclude_failed_extraction,
            exclude_expired_deadline=exclude_expired_deadline
        )
        if success:
            logger.info(f"[Output] Output saved to: {output_file}")
            if output_data and 'filter_stats' in output_data:
                stats = output_data['filter_stats']
                logger.info(f"Filter summary: {stats}")
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Keyword matching failed: {e}", exc_info=True)
        return 1


def cmd_build_digests(args):
    """Build HTML/text digests grouped by recipient email."""
    logger.info("=== Building Email Digests ===")
    
    config = get_config()
    
    # Initialize run date (06_digests)
    run_date = config.initialize_run(is_full_pipeline=False, step_name='06_digests')
    logger.info(f"[Date] Using run folder: {run_date}")

    builder = DigestBuilder(template_dir=Path(args.template_dir) if args.template_dir else None)

    # Resolve source file (from 05_match_keywords of same run)
    if args.input:
        source_file = Path(args.input)
    else:
        match_folder = config.get_dated_path('05_match_keywords', run_date)
        if not match_folder.exists():
            logger.error(f"Match keywords folder not found: {match_folder}")
            logger.error("Please run 'python main.py match-keywords' first")
            return 1
            
        # Find latest grants_by_keywords_emails_*.json
        match_files = list(match_folder.glob("grants_by_keywords_emails_*.json"))
        if not match_files:
            logger.error(f"No grants_by_keywords_emails_*.json files found in {match_folder}")
            return 1
        source_file = max(match_files, key=lambda p: p.stat().st_mtime)
        logger.info(f"Using source file: {source_file}")

    # Determine output file (in 06_digests of same run)
    if args.output:
        output_file = Path(args.output)
    else:
        digest_folder = config.ensure_dated_folder('06_digests', run_date)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = digest_folder / f"email_digests_{timestamp}.json"

    try:
        builder.build_digests(source_file, output_file)
        logger.info("=== Digest build complete ===")
        logger.info(f"[Output] Output saved to: {output_file}")
        return 0
    except Exception as e:
        logger.error(f"Digest build failed: {e}", exc_info=True)
        return 1


def cmd_clear_history(args):
    """Clear the seen URLs history."""
    logger.info("=== Clearing Seen URLs History ===")
    
    from utils.seen_urls_manager import SeenUrlsManager
    
    try:
        manager = SeenUrlsManager()
        
        # Get stats before clearing
        stats_before = manager.get_stats()
        logger.info(f"Current history: {stats_before['total_seen']} URLs")
        
        if stats_before['total_seen'] == 0:
            logger.info("History is already empty, nothing to clear")
            return 0
        
        # Confirm with user unless --force flag is set
        if not args.force:
            if args.days:
                prompt = f"\n⚠️  Cancellare gli URL degli ultimi {args.days} giorni? (y/N): "
            else:
                prompt = f"\n⚠️  Cancellare TUTTA la cronologia ({stats_before['total_seen']} URLs)? (y/N): "
            
            try:
                response = input(prompt).strip().lower()
                if response not in ['y', 'yes', 's', 'si', 'sì']:
                    logger.info("❌ Operazione annullata")
                    return 0
            except (EOFError, KeyboardInterrupt):
                logger.info("\n❌ Operazione annullata")
                return 0
        
        # Clear history
        removed = manager.clear_history(days=args.days)
        
        if args.days:
            logger.info(f"✅ Cancellati {removed} URLs degli ultimi {args.days} giorni")
        else:
            logger.info(f"✅ Cancellati tutti i {removed} URLs dalla cronologia")
        
        stats_after = manager.get_stats()
        if stats_after['total_seen'] > 0:
            logger.info(f"📚 URLs rimanenti in cronologia: {stats_after['total_seen']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to clear history: {e}", exc_info=True)
        return 1


def cmd_send_mails(args):
    """Send email digests to recipients and alert to admin."""
    logger.info("=== Starting Mail Send ===")
    
    from utils.sent_grants_manager import SentGrantsManager
    
    config = get_config()
    
    # Create sent grants manager for tracking
    sent_manager = SentGrantsManager()
    sender = MailSender(dry_run=args.dry_run, sent_grants_manager=sent_manager)

    # Resolve digest file (from most recent 06_digests folder)
    if args.input:
        digest_file = Path(args.input)
    else:
        # Find most recent run with 06_digests folder
        run_dates = config.run_date_manager.list_run_dates()
        digest_file = None
        
        for run_date in run_dates:
            digest_folder = config.run_date_manager.get_step_folder(run_date, '06_digests')
            if digest_folder.exists():
                digest_files = list(digest_folder.glob("email_digests_*.json"))
                if digest_files:
                    digest_file = max(digest_files, key=lambda p: p.stat().st_mtime)
                    logger.info(f"Using digest file from run {run_date}: {digest_file}")
                    break
        
        if digest_file is None:
            logger.error("No email_digests_*.json files found in any run folder")
            logger.error("Please run 'python main.py build-digests' first")
            return 1

    # Send digests
    try:
        send_summary = sender.send_digests(
            digest_file,
            mode=args.mode,
            test_recipients=None
        )
        logger.info(f"Digests sent: {send_summary['sent']}, Failed: {send_summary['failed']}")
        
        # Log sent grants tracking stats
        stats = sent_manager.get_stats()
        logger.info(f"Sent grants history: {stats['total_sent_records']} records for {stats['unique_urls']} URLs")
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
    
    # Initialize run date for FULL pipeline (creates new date folder)
    run_date = config.initialize_run(is_full_pipeline=True)
    logger.info(f"[Date] Created new run folder: {run_date}")
    logger.info(f"[Info] All outputs will be saved to: intermediate_outputs/{run_date}/")
    
    # Step 1: Scrape
    logger.info("\n--- Step 1/7: Scraping Links ---")
    scrape_folder = config.ensure_dated_folder('01_scrape', run_date)
    scrape_output = scrape_folder / 'all_links'
    rss_output = scrape_folder / 'rss_feeds'
    scrape_args = argparse.Namespace(
        problematic=args.problematic,
        output=str(scrape_output),
        save_json=True,
        verbose=getattr(args, 'verbose', False),
        ignore_history=getattr(args, 'ignore_history', False)
    )
    
    if cmd_scrape(scrape_args) != 0:
        logger.error("Pipeline failed at scraping step")
        return 1
    
    # Step 2: Deduplicate
    logger.info("\n--- Step 2/7: Deduplicating Links ---")
    dedup_output = config.ensure_dated_folder('02_deduplicate', run_date) / 'link_unificati.json'
    dedup_args = argparse.Namespace(
        input=str(scrape_output),
        output=str(dedup_output),
        pattern="*_links.json"
    )
    
    if cmd_deduplicate(dedup_args) != 0:
        logger.error("Pipeline failed at deduplication step")
        return 1
    
    # Step 3: Classify (without extraction)
    logger.info("\n--- Step 3/7: Classifying Links ---")
    classified_file = config.ensure_dated_folder('03_classify', run_date) / 'classified_links.json'
    classify_args = argparse.Namespace(
        input=str(dedup_output),
        output=str(classified_file),
        model=args.model,
        batch_size=args.batch_size,
        force_refresh=getattr(args, 'force_refresh', False)
    )
    
    if cmd_classify(classify_args) != 0:
        logger.error("Pipeline failed at classification step")
        return 1
    
    # Step 4: Extract
    logger.info("\n--- Step 4/7: Extracting Grant Details ---")
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    extract_output = config.ensure_dated_folder('04_extract', run_date) / f"extracted_grants_{timestamp}.json"
    extract_args = argparse.Namespace(
        input=str(classified_file),
        output=str(extract_output),
        model=args.model,
        batch_size=args.batch_size,
        force_refresh=getattr(args, 'force_refresh', False)
    )
    
    if cmd_extract(extract_args) != 0:
        logger.error("Pipeline failed at extraction step")
        return 1
    
    # Step 5: Match Keywords
    logger.info("\n--- Step 5/7: Matching Keywords to Recipients ---")
    match_output = config.ensure_dated_folder('05_match_keywords', run_date) / f"grants_by_keywords_emails_{timestamp}.json"
    match_args = argparse.Namespace(
        input=str(extract_output),
        output=str(match_output)
    )
    
    if cmd_match_keywords(match_args) != 0:
        logger.error("Pipeline failed at keyword matching step")
        return 1
    
    # Step 6: Build Digests
    logger.info("\n--- Step 6/7: Building Email Digests ---")
    digest_output = config.ensure_dated_folder('06_digests', run_date) / f"email_digests_{timestamp}.json"
    digest_args = argparse.Namespace(
        input=str(match_output),
        output=str(digest_output),
        template_dir=None
    )
    
    if cmd_build_digests(digest_args) != 0:
        logger.error("Pipeline failed at digest building step")
        return 1
    
    # Step 7: Send Mails (optional, not part of main pipeline for now)
    # User can run separately: python main.py send-mails
    
    logger.info("\n=== Pipeline Complete ===")
    logger.info(f"[Info] All outputs saved to: intermediate_outputs/{run_date}/")
    logger.info("\n💡 Next step: Send emails with 'python main.py send-mails'")
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
    parser_scrape.add_argument(
        '--ignore-history',
        action='store_true',
        help='Ignore previously seen URLs and process all links (bypasses cross-run deduplication)'
    )
    
    # Clear History command
    parser_clear = subparsers.add_parser('clear-history', help='Clear seen URLs history')
    parser_clear.add_argument(
        '--days',
        type=int,
        help='Clear only URLs from the last N days (default: clear all history)'
    )
    parser_clear.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
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
    parser_match.add_argument(
        '--retry-failed',
        action='store_true',
        default=False,
        help='If set, include grants with failed extraction (allow retry). Default: skip failed extractions'
    )
    parser_match.add_argument(
        '--include-expired',
        action='store_true',
        default=False,
        help='If set, include grants with expired deadlines (deadline < today). Default: exclude expired'
    )
    parser_match.add_argument(
        '--include-sent',
        action='store_true',
        default=False,
        help='If set, re-include grants already sent to recipients. Default: exclude previously sent'
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
    parser_pipeline.add_argument(
        '--ignore-history',
        action='store_true',
        help='Ignore previously seen URLs and process all links (bypasses cross-run deduplication)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging - use DEBUG level if verbose flag is set for any command
    log_level = 'DEBUG' if (hasattr(args, 'verbose') and args.verbose) else 'INFO'
    setup_logger('scrapiens', level=log_level)
    
    # Initialize config and ensure all directories exist with proper permissions
    try:
        config = get_config()
        config.ensure_directories()
        logger.debug("All output directories validated and ready")
    except PermissionError as e:
        logger.error(f"Directory permission error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        return 1
    
    # Execute command
    commands = {
        'scrape': cmd_scrape,
        'deduplicate': cmd_deduplicate,
        'classify': cmd_classify,
        'extract': cmd_extract,
        'match-keywords': cmd_match_keywords,
        'build-digests': cmd_build_digests,
        'send-mails': cmd_send_mails,
        'pipeline': cmd_pipeline,
        'clear-history': cmd_clear_history
    }
    
    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
