"""Site profiles management for tracking dynamic content and JavaScript-heavy sites."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
from utils.logger import get_logger

logger = get_logger(__name__)


class SiteProfileManager:
    """
    Manages site profiles to track which sites have JavaScript-loaded fields.
    
    This helps optimize scraping strategies based on past observations:
    - Sites with JS-loaded deadlines: use longer timeouts, more clicks
    - Sites with pre-rendered content: use fast HTTP-only mode
    - Sites with API-loaded data: use network monitoring
    """
    
    def __init__(self, profiles_file: Optional[str] = None):
        """
        Initialize the site profile manager.
        
        Args:
            profiles_file: Path to site_profiles.json file. 
                          If None, uses config path
        """
        if profiles_file is None:
            # Get from config
            from config.settings import get_config
            config = get_config()
            profiles_file = config.get_full_path('paths.site_profiles_file')
        
        self.profiles_file = Path(profiles_file)
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
        self.profiles: Dict[str, Dict[str, Any]] = self._load_profiles()
    
    def _load_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Load site profiles from JSON file."""
        if self.profiles_file.exists():
            try:
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load site profiles: {e}")
                return {}
        return {}
    
    def _save_profiles(self) -> None:
        """Save site profiles to JSON file."""
        try:
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save site profiles: {e}")
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc or parsed.path
    
    def get_site_profile(self, url: str) -> Dict[str, Any]:
        """
        Get the profile for a site.
        
        Args:
            url: URL to check
            
        Returns:
            Site profile dict with extraction strategies
        """
        domain = self._get_domain(url)
        
        if domain not in self.profiles:
            # Return default profile for unknown sites
            return {
                'domain': domain,
                'observations': 0,
                'deadline_extraction_success_rate': 0.5,  # Assume 50% success
                'has_js_loaded_deadline': False,
                'has_js_loaded_funding': False,
                'has_expandable_content': False,
                'recommended_timeout': 8,
                'recommended_clicks': 10,
                'last_updated': None,
                'notes': 'Unknown site'
            }
        
        return self.profiles[domain]
    
    def update_site_profile(
        self,
        url: str,
        deadline_found: bool,
        funding_found: bool,
        expandable_elements_clicked: int,
        notes: Optional[str] = None
    ) -> None:
        """
        Update a site profile based on extraction results.
        
        Args:
            url: URL processed
            deadline_found: Whether deadline was successfully extracted
            funding_found: Whether funding amount was successfully extracted
            expandable_elements_clicked: Number of UI elements clicked to reveal content
            notes: Optional notes about the extraction
        """
        domain = self._get_domain(url)
        
        # Initialize profile if new
        if domain not in self.profiles:
            self.profiles[domain] = {
                'domain': domain,
                'observations': 0,
                'deadline_extraction_success_rate': 0.0,
                'has_js_loaded_deadline': False,
                'has_js_loaded_funding': False,
                'has_expandable_content': False,
                'recommended_timeout': 8,
                'recommended_clicks': 10,
                'last_updated': None,
                'notes': notes or 'Newly observed site'
            }
        
        profile = self.profiles[domain]
        
        # Update observation count
        profile['observations'] = profile.get('observations', 0) + 1
        
        # Update success rates
        old_success = profile.get('deadline_extraction_success_rate', 0.5)
        obs = profile['observations']
        profile['deadline_extraction_success_rate'] = (
            (old_success * (obs - 1) + (1.0 if deadline_found else 0.0)) / obs
        )
        
        # Update heuristics based on observations
        if expandable_elements_clicked > 0:
            profile['has_expandable_content'] = True
            # Increase recommended clicks if we found expandable content
            profile['recommended_clicks'] = min(30, expandable_elements_clicked + 5)
        
        # If deadline not found despite clicks, likely JS-loaded
        if not deadline_found and expandable_elements_clicked > 3:
            profile['has_js_loaded_deadline'] = True
            # Increase timeout for JS-heavy sites
            profile['recommended_timeout'] = min(15, profile.get('recommended_timeout', 8) + 2)
        
        if not funding_found and expandable_elements_clicked > 3:
            profile['has_js_loaded_funding'] = True
        
        profile['last_updated'] = datetime.now().isoformat()
        if notes:
            profile['notes'] = notes
        
        self._save_profiles()
        
        logger.debug(
            f"Updated profile for {domain}: "
            f"deadline_success={profile['deadline_extraction_success_rate']:.1%}, "
            f"observations={profile['observations']}"
        )
    
    def get_recommended_settings(self, url: str) -> Dict[str, Any]:
        """
        Get recommended scraping settings based on site profile.
        
        Args:
            url: URL to scrape
            
        Returns:
            Dict with recommended settings (timeout, max_clicks, etc.)
        """
        profile = self.get_site_profile(url)
        
        settings = {
            'page_load_timeout': profile.get('recommended_timeout', 8),
            'max_expandable_clicks': profile.get('recommended_clicks', 10),
            'use_aggressive_mode': profile.get('has_js_loaded_deadline', False),
        }
        
        return settings
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about tracked sites.
        
        Returns:
            Stats dict with site counts and success rates
        """
        if not self.profiles:
            return {
                'total_sites': 0,
                'total_observations': 0,
                'avg_deadline_success_rate': 0.0,
                'sites_with_js_loaded_content': 0,
                'sites_with_expandable_content': 0,
            }
        
        total_obs = sum(p.get('observations', 0) for p in self.profiles.values())
        avg_success = (
            sum(p.get('deadline_extraction_success_rate', 0.5) for p in self.profiles.values())
            / len(self.profiles)
            if self.profiles else 0.0
        )
        
        js_sites = sum(1 for p in self.profiles.values() if p.get('has_js_loaded_deadline'))
        expandable_sites = sum(1 for p in self.profiles.values() if p.get('has_expandable_content'))
        
        return {
            'total_sites': len(self.profiles),
            'total_observations': total_obs,
            'avg_deadline_success_rate': avg_success,
            'sites_with_js_loaded_content': js_sites,
            'sites_with_expandable_content': expandable_sites,
        }
    
    def print_stats(self) -> None:
        """Print site profile statistics to logger."""
        stats = self.get_stats()
        logger.info("=== Site Profile Statistics ===")
        logger.info(f"Total sites tracked: {stats['total_sites']}")
        logger.info(f"Total observations: {stats['total_observations']}")
        logger.info(f"Avg deadline extraction rate: {stats['avg_deadline_success_rate']:.1%}")
        logger.info(f"Sites with JS-loaded content: {stats['sites_with_js_loaded_content']}")
        logger.info(f"Sites with expandable content: {stats['sites_with_expandable_content']}")
