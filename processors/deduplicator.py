"""Link deduplication and aggregation module."""

from pathlib import Path
from typing import Any, Dict, List, Set
from utils.logger import get_logger
from utils.file_utils import save_json, load_json

logger = get_logger(__name__)


def aggregate_links_with_keywords(input_dir: Path, file_pattern: str = "*_links.json") -> Dict[str, Dict[str, List[str]]]:
    """
    Aggregate all link files from a directory.
    
    Args:
        input_dir: Directory containing individual link files (JSON format)
        file_pattern: Pattern to match link files
        
    Returns:
        Dictionary mapping site names to {url: [keywords]} dictionaries
    """
    if not input_dir.exists():
        logger.warning(f"Directory not found: {input_dir}")
        return {}
    
    results = {}
    
    for file_path in input_dir.glob(file_pattern):
        site_name = file_path.stem.replace('_links', '')
        data = load_json(file_path)
        
        if data:
            results[site_name] = data
            logger.debug(f"Loaded {len(data)} links from {site_name}")
    
    logger.info(f"Aggregated links from {len(results)} sites")
    return results


def deduplicate_links(all_links: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Deduplicate links across all sites.
    
    Args:
        all_links: Dictionary mapping site names to lists of URLs
        
    Returns:
        Dictionary with:
        - unique_links: List of unique URLs (sorted)
        - stats: Statistics about deduplication
        - sites: Original site-to-links mapping
    """
    logger.info("Deduplicating links...")
    
    # Count total links before deduplication
    total_links = sum(len(links) for links in all_links.values())
    
    # Deduplicate
    unique_links = set()
    for site_name, links in all_links.items():
        unique_links.update(links)
    
    # Calculate statistics
    duplicates_removed = total_links - len(unique_links)
    
    stats = {
        'total_sites': len(all_links),
        'total_links_before': total_links,
        'unique_links': len(unique_links),
        'duplicates_removed': duplicates_removed,
        'deduplication_rate': round(duplicates_removed / total_links * 100, 2) if total_links > 0 else 0
    }
    
    logger.info(f"Deduplication complete: {stats['unique_links']} unique links from {stats['total_links_before']} total")
    logger.info(f"Removed {stats['duplicates_removed']} duplicates ({stats['deduplication_rate']}%)")
    
    return {
        'unique_links': sorted(list(unique_links)),
        'stats': stats,
        'sites': all_links
    }


def deduplicate_links_with_keywords(sites_with_keywords: Dict[str, Dict[str, List[str]]]) -> Dict[str, Any]:
    """
    Deduplicate links across all sites and output simple list without keywords.
    
    Args:
        sites_with_keywords: Dictionary mapping site names to {url: [keywords]} dictionaries
        
    Returns:
        Dictionary with:
        - links: List of unique URLs (sorted)
        - stats: Statistics about deduplication
    """
    logger.info("Deduplicating links...")
    
    # Count total links before deduplication
    total_links = sum(len(links) for links in sites_with_keywords.values())
    
    # Deduplicate: collect unique links only (no keywords)
    unique_links_set = set()
    
    for site_name, site_links in sites_with_keywords.items():
        for url in site_links.keys():
            unique_links_set.add(url)
    
    # Calculate statistics
    duplicates_removed = total_links - len(unique_links_set)
    
    stats = {
        'total_sites': len(sites_with_keywords),
        'total_links_before': total_links,
        'unique_links': len(unique_links_set),
        'duplicates_removed': duplicates_removed,
        'deduplication_rate': round(duplicates_removed / total_links * 100, 2) if total_links > 0 else 0
    }
    
    logger.info(f"Deduplication complete: {stats['unique_links']} unique links from {stats['total_links_before']} total")
    logger.info(f"Removed {stats['duplicates_removed']} duplicates ({stats['deduplication_rate']}%)")
    
    return {
        'links': sorted(list(unique_links_set)),
        'stats': stats
    }


def deduplicate_from_directory(
    input_dir: Path,
    output_file: Path,
    file_pattern: str = "*_links.json"
) -> Dict[str, Any]:
    """
    Load all link files from a directory, deduplicate (preserving keywords), and save results.
    
    Args:
        input_dir: Directory containing individual link files (JSON format)
        output_file: Path to save deduplicated results (JSON)
        file_pattern: Pattern to match link files
        
    Returns:
        Deduplication results dictionary
    """
    logger.info(f"Loading links from directory: {input_dir}")
    
    # Load all link files with keywords
    sites_with_keywords = aggregate_links_with_keywords(input_dir, file_pattern)
    
    if not sites_with_keywords:
        logger.warning("No links loaded from directory")
        return {
            'links': [],
            'stats': {
                'total_sites': 0,
                'total_links_before': 0,
                'unique_links': 0,
                'duplicates_removed': 0,
                'deduplication_rate': 0
            }
        }
    
    # Deduplicate
    results = deduplicate_links_with_keywords(sites_with_keywords)
    
    # Save results
    save_json(results, output_file)
    
    logger.info(f"Deduplication results saved to {output_file}")
    
    return results


def merge_deduplication_results(result_files: List[Path]) -> Dict[str, Any]:
    """
    Merge multiple deduplication result files.
    
    Useful for combining results from different scraping runs
    (e.g., standard and problematic sites).
    
    Args:
        result_files: List of paths to deduplication result JSON files
        
    Returns:
        Merged deduplication results
    """
    logger.info(f"Merging {len(result_files)} deduplication result files")
    
    all_sites = {}
    
    for result_file in result_files:
        if not result_file.exists():
            logger.warning(f"Result file not found: {result_file}")
            continue
        
        data = load_json(result_file)
        
        if data and 'sites' in data:
            all_sites.update(data['sites'])
    
    # Deduplicate merged results
    merged = deduplicate_links_with_keywords(all_sites)
    
    logger.info(f"Merged results: {merged['stats']['unique_links']} unique links")
    
    return merged
