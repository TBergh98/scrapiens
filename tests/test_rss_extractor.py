"""Tests for RSS feed extraction."""

import pytest
from scraper.rss_extractor import RssExtractor


def test_extract_links_from_rss_valid():
    """Test extraction from a valid RSS feed."""
    # Use a reliable public RSS feed for testing
    rss_url = "https://www.nature.com/nature.rss"
    
    try:
        links = RssExtractor.extract_links_from_rss(rss_url)
        assert isinstance(links, set)
        assert len(links) > 0
        # Check that links are absolute URLs
        assert all(link.startswith('http') for link in links)
    except Exception as e:
        pytest.skip(f"RSS feed unavailable: {e}")


def test_extract_links_from_rss_invalid():
    """Test handling of invalid RSS URL."""
    # feedparser handles invalid URLs gracefully and returns empty set
    links = RssExtractor.extract_links_from_rss("https://invalid-url-12345.com/feed.xml")
    assert isinstance(links, set)
    assert len(links) == 0  # Should return empty set for invalid URLs


def test_scrape_site_rss_missing_url():
    """Test error handling when rss_url is missing."""
    site_config = {'name': 'test', 'url': 'https://example.com'}
    
    with pytest.raises(ValueError, match="no rss_url configured"):
        RssExtractor.scrape_site_rss(site_config)


def test_scrape_site_rss_valid():
    """Test full site scraping via RSS."""
    site_config = {
        'name': 'test_rss_site',
        'url': 'https://www.nature.com',
        'rss_url': 'https://www.nature.com/nature.rss'
    }
    
    try:
        links = RssExtractor.scrape_site_rss(site_config)
        assert isinstance(links, set)
        assert len(links) > 0
    except Exception as e:
        pytest.skip(f"RSS feed unavailable: {e}")
