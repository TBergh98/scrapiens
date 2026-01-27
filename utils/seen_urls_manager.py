"""Manager for tracking URLs seen across multiple pipeline runs."""

import json
from pathlib import Path
from typing import Dict, Set, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class SeenUrlsManager:
    """Manages persistent tracking of URLs seen in previous runs."""
    
    def __init__(self, seen_urls_file: Optional[Path] = None):
        """
        Initialize the seen URLs manager.
        
        Args:
            seen_urls_file: Path to seen URLs JSON file (uses config default if None)
        """
        if seen_urls_file is None:
            from config.settings import get_config
            config = get_config()
            seen_urls_file_path = config.get_full_path('paths.seen_urls_file')
        else:
            seen_urls_file_path = seen_urls_file if isinstance(seen_urls_file, Path) else Path(seen_urls_file)
        
        self.seen_urls_file = seen_urls_file_path
        self.seen_urls: Dict[str, str] = {}  # url -> timestamp
        
        # Ensure directory exists
        self.seen_urls_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing seen URLs
        self.load_seen_urls()
        
        logger.info(f"Initialized SeenUrlsManager with file: {self.seen_urls_file}")
    
    def load_seen_urls(self) -> Dict[str, str]:
        """
        Load seen URLs from JSON file.
        
        Returns:
            Dictionary mapping URLs to first seen timestamp
        """
        if not self.seen_urls_file.exists():
            logger.info(f"Seen URLs file not found, starting fresh: {self.seen_urls_file}")
            self.seen_urls = {}
            return self.seen_urls
        
        try:
            with open(self.seen_urls_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.seen_urls = data.get('seen_urls', {})
            
            logger.info(f"Loaded {len(self.seen_urls)} seen URLs from {self.seen_urls_file}")
            return self.seen_urls
            
        except Exception as e:
            logger.error(f"Failed to load seen URLs from {self.seen_urls_file}: {e}")
            self.seen_urls = {}
            return self.seen_urls
    
    def save_seen_urls(self) -> None:
        """Save seen URLs to JSON file."""
        try:
            self.seen_urls_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'seen_urls': self.seen_urls,
                'stats': {
                    'total_seen': len(self.seen_urls),
                    'first_seen_date': min(self.seen_urls.values()) if self.seen_urls else None,
                    'last_update': datetime.now().isoformat()
                }
            }
            
            with open(self.seen_urls_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(self.seen_urls)} seen URLs to {self.seen_urls_file}")
            
        except Exception as e:
            logger.error(f"Failed to save seen URLs to {self.seen_urls_file}: {e}")
    
    def is_url_seen(self, url: str) -> bool:
        """
        Check if URL has been seen in previous runs.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL was seen before, False otherwise
        """
        return url in self.seen_urls
    
    def mark_urls_as_seen(self, urls: Set[str]) -> int:
        """
        Mark multiple URLs as seen with current timestamp.
        
        Args:
            urls: Set of URLs to mark as seen
            
        Returns:
            Number of new URLs added (excludes already seen)
        """
        timestamp = datetime.now().isoformat()
        new_count = 0
        
        for url in urls:
            if url not in self.seen_urls:
                self.seen_urls[url] = timestamp
                new_count += 1
        
        if new_count > 0:
            logger.info(f"Marked {new_count} new URLs as seen")
        
        return new_count
    
    def filter_unseen_urls(self, urls: Set[str]) -> Set[str]:
        """
        Filter out URLs that have been seen before.
        
        Args:
            urls: Set of URLs to filter
            
        Returns:
            Set of URLs not seen before
        """
        unseen = urls - self.seen_urls.keys()
        seen_count = len(urls) - len(unseen)
        
        if seen_count > 0:
            logger.info(f"Filtered out {seen_count} previously seen URLs, {len(unseen)} are new")
        
        return unseen
    
    def clear_history(self, days: Optional[int] = None) -> int:
        """
        Clear seen URLs history.
        
        Args:
            days: If specified, only clear URLs seen in the last N days.
                  If None, clear all history.
            
        Returns:
            Number of URLs removed from history
        """
        initial_count = len(self.seen_urls)
        
        if days is None:
            # Clear all history
            self.seen_urls = {}
            removed = initial_count
            logger.info(f"Cleared all {removed} URLs from history")
        else:
            # Clear only URLs from last N days
            cutoff_date = datetime.now()
            cutoff_date = cutoff_date.replace(
                day=cutoff_date.day - days if cutoff_date.day > days else 1
            )
            cutoff_timestamp = cutoff_date.isoformat()
            
            # Keep only URLs older than cutoff
            self.seen_urls = {
                url: timestamp 
                for url, timestamp in self.seen_urls.items() 
                if timestamp < cutoff_timestamp
            }
            
            removed = initial_count - len(self.seen_urls)
            logger.info(f"Cleared {removed} URLs from last {days} days, kept {len(self.seen_urls)} older URLs")
        
        # Save the updated history
        if removed > 0:
            self.save_seen_urls()
        
        return removed
    
    def get_stats(self) -> Dict:
        """
        Get statistics about seen URLs.
        
        Returns:
            Dictionary with stats
        """
        if not self.seen_urls:
            return {
                'total_seen': 0,
                'first_seen_date': None,
                'last_seen_date': None
            }
        
        timestamps = list(self.seen_urls.values())
        return {
            'total_seen': len(self.seen_urls),
            'first_seen_date': min(timestamps),
            'last_seen_date': max(timestamps)
        }
