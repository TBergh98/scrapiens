"""Scraper package initialization."""

from .excel_reader import read_sites_from_xlsx, load_sites_from_config, sanitize_domain_name
from .selenium_utils import accept_cookies, hide_overlays, scroll_page_for_lazy_content
from .pagination import handle_pagination, click_next_button, detect_page_change
from .link_extractor import scrape_sites, scrape_site, create_webdriver, extract_links_from_page

__all__ = [
    'read_sites_from_xlsx',
    'load_sites_from_config',
    'sanitize_domain_name',
    'accept_cookies',
    'hide_overlays',
    'scroll_page_for_lazy_content',
    'handle_pagination',
    'click_next_button',
    'detect_page_change',
    'scrape_sites',
    'scrape_site',
    'create_webdriver',
    'extract_links_from_page'
]
