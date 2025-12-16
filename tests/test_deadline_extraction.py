#!/usr/bin/env python3
"""
Quick validation script for deadline extraction improvements.
Tests the extraction pipeline on a sample of URLs to measure improvement.
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from processors.extractor import GrantExtractor
from utils.logger import get_logger

logger = get_logger(__name__)


def load_sample_urls(sample_file: Path, max_urls: int = 20) -> list:
    """
    Load URLs from extracted_grants JSON to test on.
    
    Args:
        sample_file: Path to extracted_grants JSON
        max_urls: Maximum number of URLs to test
        
    Returns:
        List of URLs
    """
    try:
        with open(sample_file, 'r', encoding='utf-8') as f:
            grants = json.load(f)
        
        # Get URLs with missing deadlines (good candidates for testing)
        urls_to_test = []
        
        for grant in grants[:max_urls * 2]:  # Scan more to find ones with missing deadline
            if grant.get('deadline') is None and grant.get('extraction_success'):
                urls_to_test.append(grant['url'])
        
        # If we don't have enough with missing deadlines, include some with existing ones
        if len(urls_to_test) < max_urls:
            for grant in grants:
                if grant.get('extraction_success') and len(urls_to_test) < max_urls:
                    if grant['url'] not in urls_to_test:
                        urls_to_test.append(grant['url'])
        
        return urls_to_test[:max_urls]
    
    except Exception as e:
        logger.error(f"Failed to load sample URLs: {e}")
        return []


def run_validation(sample_file: Path, max_urls: int = 20):
    """
    Run validation test on sample URLs.
    
    Args:
        sample_file: Path to extracted_grants JSON
        max_urls: Number of URLs to test
    """
    logger.info("=== DEADLINE EXTRACTION VALIDATION ===")
    logger.info(f"Testing on sample of {max_urls} URLs")
    
    # Load URLs to test
    urls = load_sample_urls(sample_file, max_urls)
    
    if not urls:
        logger.error("No URLs found to test. Check sample file.")
        return
    
    logger.info(f"Found {len(urls)} URLs to test")
    
    # Initialize extractor
    extractor = GrantExtractor()
    
    results = {
        'tested_urls': len(urls),
        'deadlines_found': 0,
        'deadlines_via_gpt': 0,
        'deadlines_via_regex': 0,
        'success_rate': 0.0,
        'test_date': datetime.now().isoformat(),
        'details': []
    }
    
    # Test each URL
    for i, url in enumerate(urls, 1):
        logger.info(f"[{i}/{len(urls)}] Testing: {url[:80]}...")
        
        try:
            grant = extractor.extract_grant_details(url)
            
            deadline = grant.get('deadline')
            has_deadline = deadline is not None
            
            result = {
                'url': url,
                'deadline_found': has_deadline,
                'deadline': deadline,
                'title': grant.get('title')[:50] if grant.get('title') else None,
                'extraction_success': grant.get('extraction_success'),
            }
            
            results['details'].append(result)
            
            if has_deadline:
                results['deadlines_found'] += 1
                logger.info(f"  ✓ Deadline found: {deadline}")
            else:
                logger.info(f"  ✗ No deadline extracted")
        
        except Exception as e:
            logger.error(f"  ✗ Extraction failed: {e}")
            results['details'].append({
                'url': url,
                'deadline_found': False,
                'deadline': None,
                'error': str(e)
            })
    
    # Calculate success rate
    results['success_rate'] = results['deadlines_found'] / results['tested_urls'] if results['tested_urls'] > 0 else 0
    
    # Print summary
    logger.info("\n=== VALIDATION RESULTS ===")
    logger.info(f"URLs tested: {results['tested_urls']}")
    logger.info(f"Deadlines found: {results['deadlines_found']}")
    logger.info(f"Success rate: {results['success_rate']:.1%}")
    
    # Print site profile stats
    logger.info("\n=== SITE PROFILE STATISTICS ===")
    extractor.site_profiles.print_stats()
    
    # Save results
    results_file = Path('intermediate_outputs/validation_results.json')
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n✓ Validation results saved to {results_file}")
    
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Validate deadline extraction improvements on a sample of URLs'
    )
    parser.add_argument(
        '--sample-file',
        type=Path,
        default=Path('intermediate_outputs/extracted_grants_20251211_162451.json'),
        help='Path to extracted_grants JSON file'
    )
    parser.add_argument(
        '--max-urls',
        type=int,
        default=20,
        help='Maximum number of URLs to test'
    )
    
    args = parser.parse_args()
    
    # Adjust path if not found
    if not args.sample_file.exists():
        # Try to find the latest extraction file
        output_dir = Path('intermediate_outputs')
        extraction_files = list(output_dir.glob('extracted_grants_*.json'))
        if extraction_files:
            args.sample_file = sorted(extraction_files)[-1]
            logger.info(f"Using latest extraction file: {args.sample_file}")
        else:
            logger.error("No extraction files found")
            exit(1)
    
    run_validation(args.sample_file, args.max_urls)
