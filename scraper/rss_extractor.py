"""RSS feed extraction module for grant sites."""

import feedparser
from typing import List, Set, Dict, Any
from urllib.parse import urljoin
from utils.logger import get_logger, timed_operation

logger = get_logger(__name__)


class RssExtractor:
    """Extract links and metadata from RSS feeds."""
    
    @staticmethod
    def _entry_to_dict(entry, base_url: str = "") -> Dict[str, Any]:
        """
        Convert a feedparser entry to a dictionary with all available fields.
        
        Args:
            entry: feedparser entry object
            base_url: Base URL for resolving relative links
            
        Returns:
            Dictionary with all entry fields (title, link, description, pubDate, etc.)
        """
        result = {}
        
        # Extract URL/link (primary field)
        url = None
        if hasattr(entry, 'link') and entry.link:
            url = urljoin(base_url, entry.link)
        elif hasattr(entry, 'links') and entry.links:
            for link_obj in entry.links:
                if isinstance(link_obj, dict) and 'href' in link_obj:
                    url = urljoin(base_url, link_obj['href'])
                    break
        
        if url:
            result['link'] = url  # Standard RSS field name
            result['url'] = url   # Also keep 'url' for backward compatibility
        
        # Extract all entry data using .keys() method (not dir())
        # FeedParserDict objects have .keys() that returns actual RSS fields
        if hasattr(entry, 'keys'):
            for key in entry.keys():
                # Skip already processed fields
                if key in ('link', 'links'):
                    continue
                
                # Skip parsed time objects (keep string versions)
                if key.endswith('_parsed'):
                    continue
                    
                try:
                    value = entry.get(key)
                    
                    # Convert complex objects to strings or skip
                    if isinstance(value, (str, int, float, bool)):
                        result[key] = value
                    elif isinstance(value, list):
                        # Handle lists (e.g., categories, tags)
                        result[key] = value
                    elif isinstance(value, dict):
                        # Handle nested dicts (e.g., title_detail, summary_detail)
                        # Extract the 'value' field if present, otherwise keep the dict
                        if 'value' in value:
                            result[key] = value['value']
                        else:
                            result[key] = value
                    elif value is not None:
                        result[key] = str(value)
                        
                except Exception as e:
                    logger.debug(f"Could not extract field '{key}': {e}")
        
        # Map common RSS fields to standard names for consistency
        # 'summary' → 'description' (standard RSS field)
        if 'summary' in result and 'description' not in result:
            result['description'] = result['summary']
        
        # 'published' → 'pubDate' (standard RSS field)
        if 'published' in result and 'pubDate' not in result:
            result['pubDate'] = result['published']
        
        # 'id' → 'guid' (standard RSS field)
        if 'id' in result and 'guid' not in result:
            result['guid'] = result['id']
                
        return result
    
    @staticmethod
    @timed_operation("RSS feed parsing")
    def extract_with_metadata(rss_url: str, base_url: str = "") -> List[Dict[str, Any]]:
        """
        Extract all entries from RSS feed with full metadata.
        
        Args:
            rss_url: URL of the RSS feed
            base_url: Base URL for resolving relative links
            
        Returns:
            List of dictionaries, each containing all available fields from RSS entry
            
        Raises:
            ValueError: If RSS feed is invalid or unreachable
        """
        logger.info(f"Fetching RSS feed with metadata: {rss_url}")
        
        try:
            feed = feedparser.parse(rss_url)
            
            # Check for parsing errors
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS feed parsing warning: {feed.bozo_exception}")
            
            if not feed.entries:
                logger.warning(f"No entries found in RSS feed: {rss_url}")
                return []
            
            entries = []
            for entry in feed.entries:
                entry_dict = RssExtractor._entry_to_dict(entry, base_url)
                if 'url' in entry_dict:  # Only include entries with valid URLs
                    entries.append(entry_dict)
            
            logger.info(f"Extracted {len(entries)} entries with metadata from RSS feed")
            return entries
            
        except Exception as e:
            logger.error(f"Failed to parse RSS feed {rss_url}: {type(e).__name__}: {e}")
            raise ValueError(f"RSS extraction failed for {rss_url}: {e}")
    
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
        Scrape a site using its RSS feed (backward compatible - returns only URLs).
        
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
    
    @staticmethod
    def scrape_site_rss_with_metadata(site_config: Dict) -> List[Dict[str, Any]]:
        """
        Scrape a site using its RSS feed with full metadata.
        
        Args:
            site_config: Site configuration dict with 'rss_url' and 'url' keys
            
        Returns:
            List of dictionaries with RSS entry metadata
        """
        rss_url = site_config.get('rss_url')
        base_url = site_config.get('url', '')
        name = site_config.get('name', 'unknown')
        
        if not rss_url:
            raise ValueError(f"Site '{name}' has no rss_url configured")
        
        logger.info(f"Scraping site '{name}' via RSS with metadata: {rss_url}")
        
        try:
            entries = RssExtractor.extract_with_metadata(rss_url, base_url)
            logger.info(f"Site '{name}': Scraped {len(entries)} entries with metadata via RSS")
            return entries
            
        except Exception as e:
            logger.error(f"RSS scraping with metadata failed for '{name}': {e}")
            # Return empty list instead of failing entire pipeline
            return []
