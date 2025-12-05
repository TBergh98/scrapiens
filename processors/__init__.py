"""Processors package initialization."""

from .deduplicator import deduplicate_links, deduplicate_links_with_keywords, deduplicate_from_directory, merge_deduplication_results
from .classifier import LinkClassifier, classify_links
from .extractor import GrantExtractor, extract_grants

__all__ = [
    'deduplicate_links',
    'deduplicate_links_with_keywords',
    'deduplicate_from_directory',
    'merge_deduplication_results',
    'LinkClassifier',
    'classify_links',
    'GrantExtractor',
    'extract_grants'
]
