"""Tests for deduplication module."""

import pytest
from processors.deduplicator import deduplicate_links


def test_deduplicate_links_empty():
    """Test deduplication with empty input."""
    result = deduplicate_links({})
    
    assert result['unique_links'] == []
    assert result['stats']['total_sites'] == 0
    assert result['stats']['total_links_before'] == 0
    assert result['stats']['unique_links'] == 0
    assert result['stats']['duplicates_removed'] == 0


def test_deduplicate_links_no_duplicates():
    """Test deduplication when there are no duplicates."""
    all_links = {
        'site1': ['http://example.com/1', 'http://example.com/2'],
        'site2': ['http://example.com/3', 'http://example.com/4']
    }
    
    result = deduplicate_links(all_links)
    
    assert len(result['unique_links']) == 4
    assert result['stats']['total_sites'] == 2
    assert result['stats']['total_links_before'] == 4
    assert result['stats']['unique_links'] == 4
    assert result['stats']['duplicates_removed'] == 0
    assert result['stats']['deduplication_rate'] == 0


def test_deduplicate_links_with_duplicates():
    """Test deduplication when there are duplicates."""
    all_links = {
        'site1': ['http://example.com/1', 'http://example.com/2', 'http://example.com/3'],
        'site2': ['http://example.com/2', 'http://example.com/3', 'http://example.com/4']
    }
    
    result = deduplicate_links(all_links)
    
    assert len(result['unique_links']) == 4
    assert set(result['unique_links']) == {
        'http://example.com/1',
        'http://example.com/2',
        'http://example.com/3',
        'http://example.com/4'
    }
    assert result['stats']['total_sites'] == 2
    assert result['stats']['total_links_before'] == 6
    assert result['stats']['unique_links'] == 4
    assert result['stats']['duplicates_removed'] == 2
    assert result['stats']['deduplication_rate'] == pytest.approx(33.33, rel=0.01)


def test_deduplicate_links_all_duplicates():
    """Test deduplication when all links are duplicates."""
    all_links = {
        'site1': ['http://example.com/1', 'http://example.com/1'],
        'site2': ['http://example.com/1', 'http://example.com/1']
    }
    
    result = deduplicate_links(all_links)
    
    assert len(result['unique_links']) == 1
    assert result['unique_links'][0] == 'http://example.com/1'
    assert result['stats']['total_links_before'] == 4
    assert result['stats']['unique_links'] == 1
    assert result['stats']['duplicates_removed'] == 3
    assert result['stats']['deduplication_rate'] == 75.0
