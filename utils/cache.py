"""Cache management for extracted grant details."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class CacheManager:
    """Manages persistent caching of extracted grant details."""
    
    def __init__(self, cache_file: Optional[Path] = None):
        """
        Initialize the cache manager.
        
        Args:
            cache_file: Path to cache JSON file (uses config default if None)
        """
        if cache_file is None:
            from config.settings import get_config
            config = get_config()
            cache_file_path = config.get_full_path('paths.grants_cache_file')
        else:
            cache_file_path = cache_file if isinstance(cache_file, Path) else Path(cache_file)
        
        self.cache_file = cache_file_path
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        # Ensure cache directory exists
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing cache
        self.load_cache()
        
        logger.info(f"Initialized CacheManager with file: {self.cache_file}")
    
    def load_cache(self) -> Dict[str, Dict[str, Any]]:
        """
        Load cache from JSON file.
        
        Returns:
            Dictionary mapping URLs to cached grant details
        """
        if not self.cache_file.exists():
            logger.info(f"Cache file not found, starting with empty cache: {self.cache_file}")
            self.cache = {}
            return self.cache
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)
            
            logger.info(f"Loaded {len(self.cache)} cached grants from {self.cache_file}")
            return self.cache
            
        except Exception as e:
            logger.error(f"Failed to load cache from {self.cache_file}: {e}")
            self.cache = {}
            return self.cache
    
    def save_cache(self) -> None:
        """Save cache to JSON file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(self.cache)} grants to cache: {self.cache_file}")
            
        except Exception as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {e}")
    
    def get_cached_grant(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get cached grant details for a URL.
        
        Args:
            url: URL to lookup
            
        Returns:
            Cached grant details or None if not found
        """
        cached = self.cache.get(url)
        
        if cached:
            logger.debug(f"Cache hit for: {url}")
            return cached
        
        logger.debug(f"Cache miss for: {url}")
        return None
    
    def update_cache(self, url: str, grant_details: Dict[str, Any]) -> None:
        """
        Update cache with new grant details.
        
        Args:
            url: URL of the grant
            grant_details: Extracted grant details dictionary
        """
        self.cache[url] = grant_details
        logger.debug(f"Updated cache for: {url}")
        
        # Save to disk immediately for persistence
        self.save_cache()
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.cache = {}
        logger.info("Cleared all cache data")
        self.save_cache()
    
    def remove_from_cache(self, url: str) -> bool:
        """
        Remove a specific URL from cache.
        
        Args:
            url: URL to remove
            
        Returns:
            True if removed, False if not found
        """
        if url in self.cache:
            del self.cache[url]
            logger.info(f"Removed from cache: {url}")
            self.save_cache()
            return True
        
        return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.
        
        Returns:
            Dictionary with cache statistics
        """
        total = len(self.cache)
        successful = sum(1 for v in self.cache.values() if v.get('extraction_success', False))
        failed = total - successful
        
        # Calculate date range
        dates = [v.get('extraction_date') for v in self.cache.values() if v.get('extraction_date') is not None]
        filtered_dates = [d for d in dates if d is not None]
        
        oldest = min(filtered_dates) if filtered_dates else None
        newest = max(filtered_dates) if filtered_dates else None
        
        return {
            'total_cached': total,
            'successful_extractions': successful,
            'failed_extractions': failed,
            'oldest_entry': oldest,
            'newest_entry': newest,
            'cache_file': str(self.cache_file),
            'cache_file_exists': self.cache_file.exists()
        }


def get_cache_manager(cache_file: Optional[Path] = None) -> CacheManager:
    """
    Get or create a cache manager instance.
    
    Args:
        cache_file: Optional path to cache file
        
    Returns:
        CacheManager instance
    """
    return CacheManager(cache_file=cache_file)
