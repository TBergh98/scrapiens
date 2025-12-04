"""File utilities for Scrapiens."""

import json
from pathlib import Path
from typing import List, Set, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)


def save_links_to_file(links: Set[str], output_path: Path) -> None:
    """
    Save a set of links to a text file, one per line, sorted.
    
    Args:
        links: Set of URL strings
        output_path: Path to output file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for link in sorted(links):
            f.write(link + '\n')
    
    logger.info(f"Saved {len(links)} links to {output_path}")


def load_links_from_file(input_path: Path) -> Set[str]:
    """
    Load links from a text file.
    
    Args:
        input_path: Path to input file
        
    Returns:
        Set of URL strings
    """
    if not input_path.exists():
        logger.warning(f"File not found: {input_path}")
        return set()
    
    with open(input_path, 'r', encoding='utf-8') as f:
        links = {line.strip() for line in f if line.strip()}
    
    logger.info(f"Loaded {len(links)} links from {input_path}")
    return links


def save_json(data: Any, output_path: Path, indent: int = 2) -> None:
    """
    Save data to JSON file.
    
    Args:
        data: Data to save (must be JSON serializable)
        output_path: Path to output file
        indent: JSON indentation level
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    
    logger.info(f"Saved JSON data to {output_path}")


def load_json(input_path: Path) -> Any:
    """
    Load data from JSON file.
    
    Args:
        input_path: Path to input file
        
    Returns:
        Parsed JSON data
    """
    if not input_path.exists():
        logger.warning(f"File not found: {input_path}")
        return None
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"Loaded JSON data from {input_path}")
    return data


def aggregate_link_files(directory: Path, pattern: str = "*_links.txt") -> Dict[str, List[str]]:
    """
    Aggregate all link files from a directory.
    
    Args:
        directory: Directory containing link files
        pattern: File pattern to match
        
    Returns:
        Dictionary mapping site names to lists of links
    """
    if not directory.exists():
        logger.warning(f"Directory not found: {directory}")
        return {}
    
    results = {}
    
    for file_path in directory.glob(pattern):
        site_name = file_path.stem.replace('_links', '')
        links = list(load_links_from_file(file_path))
        results[site_name] = links
        logger.debug(f"Loaded {len(links)} links from {site_name}")
    
    logger.info(f"Aggregated links from {len(results)} sites")
    return results


def ensure_directory(path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path
        
    Returns:
        The path (for chaining)
    """
    path.mkdir(parents=True, exist_ok=True)
    return path
