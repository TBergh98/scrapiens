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
    def all_config(self) -> Dict[str, Any]:
        """Get the entire configuration dictionary."""
        return self._config.copy()


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
