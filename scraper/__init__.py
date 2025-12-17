"""Scraper package initialization."""

from .sites_reader import load_sites_from_yaml, validate_sites_yaml
from .keywords_reader import load_keywords_from_yaml, create_keyword_to_recipients_map, get_recipients_for_keywords, validate_keywords_yaml
from .selenium_utils import accept_cookies, hide_overlays, scroll_page_for_lazy_content
from .pagination import handle_pagination, click_next_button, detect_page_change
from .link_extractor import scrape_sites, scrape_site, create_webdriver, extract_links_from_page
from .rss_extractor import RssExtractor

__all__ = [
    'load_sites_from_yaml',
    'validate_sites_yaml',
    'load_keywords_from_yaml',
    'create_keyword_to_recipients_map',
    'get_recipients_for_keywords',
    'validate_keywords_yaml',
    'accept_cookies',
    'hide_overlays',
    'scroll_page_for_lazy_content',
    'handle_pagination',
    'click_next_button',
    'detect_page_change',
    'scrape_sites',
    'scrape_site',
    'create_webdriver',
    'extract_links_from_page',
    'RssExtractor'
]

