"""Processors package initialization."""

from .deduplicator import deduplicate_links, deduplicate_links_with_keywords, deduplicate_from_directory, merge_deduplication_results
from .classifier import LinkClassifier, classify_links
from .extractor import GrantExtractor, extract_grants
from .mailer import DigestBuilder, build_email_digests
from .mail_sender import MailSender, send_emails

__all__ = [
    'deduplicate_links',
    'deduplicate_links_with_keywords',
    'deduplicate_from_directory',
    'merge_deduplication_results',
    'LinkClassifier',
    'classify_links',
    'GrantExtractor',
    'extract_grants',
    'DigestBuilder',
    'build_email_digests',
    'MailSender',
    'send_emails'
]
