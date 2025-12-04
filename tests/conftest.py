"""Test configuration and fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_links():
    """Provide sample links for testing."""
    return [
        'https://example.com/grant/2024/research-funding',
        'https://example.org/calls/list',
        'https://example.net/about-us',
        'https://example.com/grant/2023/innovation-award',
        'https://example.org/contact'
    ]


@pytest.fixture
def sample_site_config():
    """Provide sample site configuration for testing."""
    return {
        'name': 'example_com',
        'url': 'https://example.com/grants',
        'js': False,
        'next_selector': None,
        'max_pages': 1
    }


@pytest.fixture
def sample_dedup_data():
    """Provide sample deduplication data."""
    return {
        'site1': [
            'https://example.com/1',
            'https://example.com/2',
            'https://example.com/3'
        ],
        'site2': [
            'https://example.com/2',
            'https://example.com/4'
        ]
    }
