"""RSS feed extraction module for grant sites."""

import feedparser
from typing import List, Set, Dict, Any
from urllib.parse import urljoin
from utils.logger import get_logger, timed_operation

logger = get_logger(__name__)


class RssExtractor:
    """Extract links from RSS feeds with same output format as Selenium scraper."""
    
    @staticmethod
    @timed_operation("RSS feed parsing")
    def extract_links_from_rss(rss_url: str, base_url: str = "") -> Set[str]:
        """
        Extract all links from an RSS feed.
        
        Args:
            rss_url: URL of the RSS feed
            base_url: Base URL for resolving relative links
            
        Returns:
            Set of absolute URLs found in the feed
            
        Raises:
            ValueError: If RSS feed is invalid or unreachable
        """
        logger.info(f"Fetching RSS feed: {rss_url}")
        
        try:
            feed = feedparser.parse(rss_url)
            
            # Check for parsing errors
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS feed parsing warning: {feed.bozo_exception}")
            
            if not feed.entries:
                logger.warning(f"No entries found in RSS feed: {rss_url}")
                return set()
            
            links = set()
            
            for entry in feed.entries:
                # Primary link from entry.link
                if hasattr(entry, 'link') and entry.link:
                    absolute_url = urljoin(base_url, entry.link)
                    links.add(absolute_url)
                
                # Alternative links from entry.links (some feeds have multiple)
                if hasattr(entry, 'links'):
                    for link_obj in entry.links:
                        if isinstance(link_obj, dict) and 'href' in link_obj:
                            absolute_url = urljoin(base_url, link_obj['href'])
                            links.add(absolute_url)
            
            logger.info(f"Extracted {len(links)} unique links from RSS feed")
            return links
            
        except Exception as e:
            logger.error(f"Failed to parse RSS feed {rss_url}: {type(e).__name__}: {e}")
            raise ValueError(f"RSS extraction failed for {rss_url}: {e}")
    
    @staticmethod
    def scrape_site_rss(site_config: Dict) -> Set[str]:
        """
        Scrape a site using its RSS feed.
        
        Args:
            site_config: Site configuration dict with 'rss_url' and 'url' keys
            
        Returns:
            Set of extracted URLs
        """
        rss_url = site_config.get('rss_url')
        base_url = site_config.get('url', '')
        name = site_config.get('name', 'unknown')
        
        if not rss_url:
            raise ValueError(f"Site '{name}' has no rss_url configured")
        
        logger.info(f"Scraping site '{name}' via RSS: {rss_url}")
        
        try:
            links = RssExtractor.extract_links_from_rss(rss_url, base_url)
            logger.info(f"Site '{name}': Scraped {len(links)} links via RSS")
            return links
            
        except Exception as e:
            logger.error(f"RSS scraping failed for '{name}': {e}")
            # Return empty set instead of failing entire pipeline
            return set()
