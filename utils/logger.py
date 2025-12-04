"""Logging utilities for Scrapiens."""

import logging
import sys
from pathlib import Path
from typing import Optional
from config.settings import get_config


def setup_logger(
    name: str,
    log_file: Optional[Path] = None,
    level: Optional[str] = None,
    log_format: Optional[str] = None
) -> logging.Logger:
    """
    Set up a logger with console and optional file output.
    
    Args:
        name: Logger name
        log_file: Path to log file (optional, overrides config)
        level: Logging level (optional, overrides config)
        log_format: Log format string (optional, overrides config)
        
    Returns:
        Configured logger instance
    """
    config = get_config()
    
    # Get configuration values
    if level is None:
        level = config.get('logging.level', 'INFO')
    if log_format is None:
        log_format = config.get(
            'logging.format',
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper() if isinstance(level, str) else 'INFO'))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if configured)
    log_to_file = config.get('logging.log_to_file', False)
    if log_to_file:
        if log_file is None:
            log_file_name = config.get('logging.log_file', 'scrapiens.log')
            log_file = config.get_path('paths.base_dir') / log_file_name
        
        # Ensure log directory exists
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create a new one with default configuration.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # If logger has no handlers, set it up
    if not logger.handlers:
        logger = setup_logger(name)
    
    return logger
