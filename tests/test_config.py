"""Tests for configuration module."""

import pytest
from pathlib import Path
from config.settings import Config


def test_config_get_simple():
    """Test getting simple configuration values."""
    config = Config()
    
    # Test getting selenium headless setting
    assert isinstance(config.get('selenium.headless'), bool)


def test_config_get_default():
    """Test getting configuration with default value."""
    config = Config()
    
    # Test non-existent key returns default
    assert config.get('nonexistent.key', 'default_value') == 'default_value'
    assert config.get('another.missing.key', 42) == 42


def test_config_get_nested():
    """Test getting nested configuration values."""
    config = Config()
    
    # Test nested paths
    model = config.get('openai.model')
    assert model is not None
    assert isinstance(model, str)


def test_config_get_path():
    """Test getting path configuration."""
    config = Config()
    
    # Test getting a path value
    base_dir = config.get_path('paths.base_dir')
    assert isinstance(base_dir, Path)
