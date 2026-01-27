"""Configuration management module for Scrapiens."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv


class Config:
    """Configuration manager that loads settings from YAML and environment variables."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to config.yaml file. If None, looks in config/ directory.
        """
        # Load environment variables from .env file
        load_dotenv()
        
        # Determine config file path
        if config_path is None:
            # Default to config/config.yaml relative to project root
            project_root = Path(__file__).parent.parent
            config_path = str(project_root / "config" / "config.yaml")
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        
        # Load configuration
        self._load_config()
        
        # Override with environment variables where applicable
        self._apply_env_overrides()
        
        # Initialize run date manager (lazy initialization)
        self._run_date_manager = None
        self._current_run_date: Optional[str] = None
    
    def _load_config(self):
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to configuration."""
        # Override BASE_DIR if set in environment
        base_dir_env = os.getenv('BASE_DIR')
        if base_dir_env:
            self._config['paths']['base_dir'] = base_dir_env
        
        # Override OPENAI_API_KEY
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            if 'openai' not in self._config:
                self._config['openai'] = {}
            self._config['openai']['api_key'] = openai_key
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'paths.base_dir')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
            
        Example:
            >>> config.get('selenium.headless')
            True
            >>> config.get('paths.output_dir')
            'all_links'
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_path(self, key: str) -> Path:
        """
        Get a path configuration value as a Path object.
        
        Args:
            key: Configuration key (e.g., 'paths.base_dir')
            
        Returns:
            Path object
        """
        value = self.get(key)
        if value is None:
            raise ValueError(f"Path configuration not found: {key}")
        return Path(value)
    
    def get_full_path(self, path_key: str) -> Path:
        """
        Get a full path by combining base_dir with the specified path.
        
        Args:
            path_key: Configuration key for the path (e.g., 'paths.output_dir')
            
        Returns:
            Full path as Path object
        """
        base_dir = self.get_path('paths.base_dir')
        relative_path = self.get(path_key)
        
        if relative_path is None:
            raise ValueError(f"Path configuration not found: {path_key}")
        
        return base_dir / relative_path
    
    @property
    def openai_api_key(self) -> str:
        """Get OpenAI API key from configuration."""
        api_key = self.get('openai.api_key')
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Please set it in .env file or as environment variable."
            )
        return api_key
    
    @property
    def smtp_config(self) -> Dict[str, Any]:
        """Get SMTP configuration for mail sending."""
        return {
            'server': os.getenv('MAILJET_SMTP_SERVER', ''),
            'port': int(os.getenv('MAILJET_SMTP_PORT', 25)),
            'login_user': os.getenv('MAILJET_LOGIN_USER', ''),
            'login_pw': os.getenv('MAILJET_LOGIN_PW', ''),
            'use_tls': str(os.getenv('MAILJET_USE_TLS', 'true')).lower() in ['1', 'true', 'yes', 'on'],
            'from_addr': os.getenv('MAIL_FROM', os.getenv('ALERT_EMAIL', '')),
            'reply_to': os.getenv('MAIL_REPLY_TO', ''),
        }
    
    @property
    def alert_email(self) -> str:
        """Get the alert/summary email address."""
        email = os.getenv('ALERT_EMAIL', '')
        if not email:
            raise ValueError(
                "ALERT_EMAIL not found. Please set it in .env file or as environment variable."
            )
        return email
    
    @property
    def all_config(self) -> Dict[str, Any]:
        """Get the entire configuration dictionary."""
        return self._config.copy()
    
    @property
    def run_date_manager(self):
        """Get or create the run date manager instance."""
        if self._run_date_manager is None:
            from utils.run_date_manager import RunDateManager
            base_dir = self.get_path('paths.base_dir')
            self._run_date_manager = RunDateManager(base_dir)
        return self._run_date_manager
    
    def set_run_date(self, run_date: str):
        """
        Set the current run date for this session.
        
        Args:
            run_date: Date string in YYYYMMDD format
        """
        self._current_run_date = run_date
    
    def get_run_date(self) -> Optional[str]:
        """
        Get the current run date for this session.
        
        Returns:
            Date string in YYYYMMDD format, or None if not set
        """
        return self._current_run_date
    
    def get_dated_path(self, step_name: str, run_date: Optional[str] = None) -> Path:
        """
        Get the full path to a step folder for the current or specified run.
        
        Args:
            step_name: Step folder name (e.g., '01_scrape', '04_extract')
            run_date: Specific run date, or None to use current session run date
            
        Returns:
            Path to intermediate_outputs/YYYYMMDD/step_name/
            
        Raises:
            ValueError: If run_date is not set and not provided
        """
        if run_date is None:
            run_date = self._current_run_date
        
        if run_date is None:
            raise ValueError(
                "Run date not set. Call set_run_date() or provide run_date parameter."
            )
        
        return self.run_date_manager.get_step_folder(run_date, step_name)
    
    def ensure_dated_folder(self, step_name: str, run_date: Optional[str] = None) -> Path:
        """
        Ensure a dated step folder exists and return its path.
        
        Args:
            step_name: Step folder name (e.g., '01_scrape')
            run_date: Specific run date, or None to use current session run date
            
        Returns:
            Path to the created/existing step folder
        """
        if run_date is None:
            run_date = self._current_run_date
        
        if run_date is None:
            raise ValueError(
                "Run date not set. Call set_run_date() or provide run_date parameter."
            )
        
        return self.run_date_manager.ensure_step_folder(run_date, step_name)
    
    def initialize_run(self, is_full_pipeline: bool = False, step_name: Optional[str] = None) -> str:
        """
        Initialize a run by determining the appropriate run date.
        
        Args:
            is_full_pipeline: True if running full pipeline
            step_name: Name of the step being executed
            
        Returns:
            Run date string in YYYYMMDD format
        """
        run_date = self.run_date_manager.get_current_run_date(
            is_full_pipeline=is_full_pipeline,
            step_name=step_name
        )
        self.set_run_date(run_date)
        return run_date
    
    def ensure_directories(self):
        """
        Ensure all output directories exist and are writable.
        Creates directories if they don't exist.
        
        Raises:
            PermissionError: If directories cannot be created or are not writable
        """
        directories_to_check = [
            'paths.output_scrape_dir',
            'paths.output_dir',
            'paths.rss_feeds_dir',
            'paths.output_deduplicate_dir',
            'paths.output_classify_dir',
            'paths.output_extract_dir',
            'paths.output_match_keywords_dir',
            'paths.output_digests_dir',
        ]
        
        base_dir = self.get_path('paths.base_dir')
        
        for dir_key in directories_to_check:
            relative_path = self.get(dir_key)
            if relative_path:
                full_path = base_dir / relative_path
                try:
                    full_path.mkdir(parents=True, exist_ok=True)
                    # Test write access
                    test_file = full_path / '.write_test'
                    test_file.touch()
                    test_file.unlink()
                except (PermissionError, OSError) as e:
                    raise PermissionError(
                        f"Cannot create or write to directory {full_path}: {e}"
                    )


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    Get or create the global configuration instance.
    
    Args:
        config_path: Path to config file (only used on first call)
        
    Returns:
        Config instance
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = Config(config_path)
    
    return _config_instance


def reload_config(config_path: Optional[str] = None):
    """
    Reload configuration from file.
    
    Args:
        config_path: Path to config file
    """
    global _config_instance
    _config_instance = Config(config_path)
