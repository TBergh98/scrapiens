"""YAML reader module for loading website configurations."""

from pathlib import Path
from typing import List, Dict, Any
import yaml
from utils.logger import get_logger

logger = get_logger(__name__)


def load_sites_from_yaml(yaml_path: Path) -> List[Dict[str, Any]]:
    """
    Load website configurations from a YAML file.
    
    Args:
        yaml_path: Path to sites.yaml file
        
    Returns:
        List of site configuration dictionaries with keys:
        - name: Site identifier (should be unique)
        - url: Full URL to scrape
        - js: Boolean indicating if JavaScript rendering needed
        - next_selector: CSS selector for pagination button (None if no pagination)
        - max_pages: Maximum pages to scrape
        - pagination_param: URL parameter to increment for pagination (optional)
        
    Raises:
        FileNotFoundError: If YAML file not found
        ValueError: If YAML is malformed or missing required fields
        
    Example YAML format:
        sites:
          - name: example_site
            url: https://example.com?page=1
            js: false
            next_selector: null
            max_pages: 5
            pagination_param: "page"
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"Sites YAML file not found: {yaml_path}")
    
    logger.info(f"Loading sites from YAML: {yaml_path}")
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML file {yaml_path}: {e}")
    
    if not data or 'sites' not in data:
        raise ValueError(f"YAML file must contain 'sites' key at root level")
    
    sites = []
    sites_list = data.get('sites', [])
    
    if not isinstance(sites_list, list):
        raise ValueError(f"'sites' must be a list, got {type(sites_list)}")
    
    for idx, site_config in enumerate(sites_list):
        try:
            # Validate required fields
            required_fields = ['name', 'url']
            for field in required_fields:
                if field not in site_config:
                    raise ValueError(f"Site at index {idx} missing required field: {field}")
            
            # Validate and get optional fields with defaults
            js = site_config.get('js', False)
            if not isinstance(js, bool):
                raise ValueError(f"Site '{site_config['name']}': 'js' must be boolean, got {type(js)}")
            
            next_selector = site_config.get('next_selector', None)
            if next_selector is not None and not isinstance(next_selector, str):
                raise ValueError(f"Site '{site_config['name']}': 'next_selector' must be string or null, got {type(next_selector)}")
            
            max_pages = site_config.get('max_pages', 1)
            if not isinstance(max_pages, int) or max_pages < 1:
                raise ValueError(f"Site '{site_config['name']}': 'max_pages' must be positive integer, got {max_pages}")
            
            pagination_param = site_config.get('pagination_param', None)
            if pagination_param is not None and not isinstance(pagination_param, str):
                raise ValueError(f"Site '{site_config['name']}': 'pagination_param' must be string or null, got {type(pagination_param)}")
            
            # RSS feed URL (optional)
            rss_url = site_config.get('rss_url', None)
            if rss_url is not None and not isinstance(rss_url, str):
                raise ValueError(f"Site '{site_config['name']}': 'rss_url' must be string or null")
            
            site = {
                'name': str(site_config['name']).strip(),
                'url': str(site_config['url']).strip(),
                'rss_url': rss_url.strip() if rss_url else None,
                'js': js,
                'next_selector': next_selector,
                'max_pages': max_pages,
                'pagination_param': pagination_param
            }
            
            sites.append(site)
            logger.debug(f"Loaded site: {site['name']} -> {site['url']}")
            
        except (KeyError, TypeError) as e:
            raise ValueError(f"Site at index {idx} has invalid structure: {e}")
    
    if not sites:
        logger.warning("No sites loaded from YAML file")
    else:
        logger.info(f"Successfully loaded {len(sites)} sites from YAML")
    
    return sites


def validate_sites_yaml(sites: List[Dict[str, Any]]) -> bool:
    """
    Validate loaded sites list.
    
    Args:
        sites: List of site dictionaries
        
    Returns:
        True if all sites are valid
        
    Raises:
        ValueError: If any site is invalid
    """
    if not isinstance(sites, list):
        raise ValueError("Sites must be a list")
    
    seen_names = set()
    for idx, site in enumerate(sites):
        if not isinstance(site, dict):
            raise ValueError(f"Site at index {idx} is not a dictionary")
        
        required = ['name', 'url', 'rss_url', 'js', 'next_selector', 'max_pages', 'pagination_param']
        if not all(key in site for key in required):
            raise ValueError(f"Site at index {idx} missing required keys: {required}")
        
        # Check for duplicate names
        if site['name'] in seen_names:
            raise ValueError(f"Duplicate site name: {site['name']}")
        seen_names.add(site['name'])
    
    return True
