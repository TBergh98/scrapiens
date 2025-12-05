"""HTTP-based link extraction for non-JavaScript sites (much faster than Selenium)."""

import time
from typing import Set, Dict
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.logger import get_logger, timed_operation, log_milestone
from config.settings import get_config

logger = get_logger(__name__)


def create_session() -> requests.Session:
    """
    Create a requests session with retry strategy and proper headers.
    
    Returns:
        Configured requests Session
    """
    session = requests.Session()
    
    # Retry strategy
    retry_strategy = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Headers to mimic browser
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    return session


def detect_js_requirement(url: str, site_name: str, timeout: int = 10) -> Dict[str, any]:
    """
    Auto-detect if a site needs JavaScript by comparing HTTP vs expected content.
    
    Strategy:
    - Try HTTP request first
    - If we get very few links (< 10) or error, likely needs JS
    - If we get many links, likely static HTML
    
    Args:
        url: URL to check
        site_name: Site name for logging
        timeout: Request timeout
        
    Returns:
        Dict with keys: needs_js (bool), http_links (int), reason (str)
    """
    try:
        session = create_session()
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        http_links = len(soup.find_all('a', href=True))
        
        # Check for common JS framework markers
        html_content = str(soup)
        js_indicators = [
            'react' in html_content.lower(),
            'angular' in html_content.lower(),
            'vue' in html_content.lower(),
            '__NEXT_DATA__' in html_content,
            'ng-app' in html_content,
            'data-reactroot' in html_content,
        ]
        
        has_js_framework = any(js_indicators)
        
        session.close()
        
        # Decision logic
        if http_links < 5:
            return {
                'needs_js': True,
                'http_links': http_links,
                'reason': f'Very few links found via HTTP ({http_links})'
            }
        elif has_js_framework and http_links < 30:
            return {
                'needs_js': True,
                'http_links': http_links,
                'reason': 'JS framework detected with limited static content'
            }
        else:
            return {
                'needs_js': False,
                'http_links': http_links,
                'reason': f'Sufficient static content found ({http_links} links)'
            }
            
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout checking {url}, assuming JS needed")
        return {'needs_js': True, 'http_links': 0, 'reason': 'HTTP timeout'}
    except requests.exceptions.RequestException as e:
        logger.warning(f"HTTP error checking {url}: {e}, assuming JS needed")
        return {'needs_js': True, 'http_links': 0, 'reason': f'HTTP error: {str(e)[:50]}'}
    except Exception as e:
        logger.warning(f"Error detecting JS requirement for {url}: {e}")
        return {'needs_js': True, 'http_links': 0, 'reason': f'Detection error: {str(e)[:50]}'}


@timed_operation("HTTP link extraction")
def extract_links_from_http(url: str, site_name: str, timeout: int = 10) -> Set[str]:
    """
    Extract all links from a page using HTTP requests (for non-JS sites).
    Much faster than Selenium!
    
    Args:
        url: URL to scrape
        site_name: Name of site (for logging)
        timeout: Request timeout in seconds
        
    Returns:
        Set of extracted URLs (all absolute)
    """
    links = set()
    
    try:
        session = create_session()
        
        start_time = time.time()
        response = session.get(url, timeout=timeout)
        elapsed = time.time() - start_time
        
        response.raise_for_status()
        
        log_milestone(f"Downloaded page for {site_name}", elapsed, "↓")
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract all links and convert to absolute URLs
        for a in soup.find_all('a'):
            href = a.get('href')
            
            # Try standard href first
            if href:
                # Convert relative URLs to absolute
                absolute_url = urljoin(url, href)
                
                # Filter out anchors, mailto, javascript, etc
                if absolute_url.startswith(('http://', 'https://')):
                    links.add(absolute_url)
            else:
                # Check for JS-based link attributes (data-href, ng-click with URL patterns, etc)
                data_href = a.get('data-href')
                data_url = a.get('data-url')
                
                if data_href:
                    absolute_url = urljoin(url, data_href)
                    if absolute_url.startswith(('http://', 'https://')):
                        links.add(absolute_url)
                elif data_url:
                    absolute_url = urljoin(url, data_url)
                    if absolute_url.startswith(('http://', 'https://')):
                        links.add(absolute_url)
        
        logger.info(f"Extracted {len(links)} links from {site_name} via HTTP")
        
        session.close()
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching {url}: {e}")
    except Exception as e:
        logger.error(f"Error extracting links from {site_name}: {e}")
    
    return links
