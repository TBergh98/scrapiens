"""Tests for deduplication module (keywords-aware)."""

import pytest
from processors.deduplicator import deduplicate_links_with_keywords


def test_deduplicate_links_empty():
    """Handles empty input gracefully."""
    result = deduplicate_links_with_keywords({})
    
    assert result['links_with_keywords'] == {}
    assert result['stats']['total_sites'] == 0
    assert result['stats']['total_links_before'] == 0
    assert result['stats']['unique_links'] == 0
    assert result['stats']['duplicates_removed'] == 0


def test_deduplicate_links_no_duplicates():
    """No duplicates should preserve keywords per link."""
    all_links = {
        'site1': {'http://example.com/1': ['bio'], 'http://example.com/2': ['ricerca']},
        'site2': {'http://example.com/3': ['ai'], 'http://example.com/4': ['ml']}
    }
    
    result = deduplicate_links_with_keywords(all_links)
    
    assert len(result['links_with_keywords']) == 4
    assert result['stats']['total_sites'] == 2
    assert result['stats']['total_links_before'] == 4
    assert result['stats']['unique_links'] == 4
    assert result['stats']['duplicates_removed'] == 0
    assert result['stats']['deduplication_rate'] == 0
    assert result['links_with_keywords']['http://example.com/1'] == ['bio']


def test_deduplicate_links_with_duplicates():
    """Duplicates merge keyword lists (union, sorted)."""
    all_links = {
        'site1': {
            'http://example.com/1': ['bio'],
            'http://example.com/2': ['ricerca'],
        },
        'site2': {
            'http://example.com/2': ['sostenibilita'],
            'http://example.com/3': ['ai'],
        },
    }
    
    result = deduplicate_links_with_keywords(all_links)
    
    assert len(result['links_with_keywords']) == 3
    assert set(result['links_with_keywords']['http://example.com/2']) == {'ricerca', 'sostenibilita'}
    assert result['stats']['duplicates_removed'] == 1
    assert result['stats']['unique_links'] == 3


def test_deduplicate_links_all_duplicates():
    """All duplicates collapse into one entry with merged keywords."""
    all_links = {
        'site1': {'http://example.com/1': ['bio']},
        'site2': {'http://example.com/1': ['ricerca']},
    }
    
    result = deduplicate_links_with_keywords(all_links)
    
    assert len(result['links_with_keywords']) == 1
    assert set(result['links_with_keywords']['http://example.com/1']) == {'bio', 'ricerca'}
    assert result['stats']['total_links_before'] == 2
    assert result['stats']['unique_links'] == 1
    assert result['stats']['duplicates_removed'] == 1
