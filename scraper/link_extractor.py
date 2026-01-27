"""Main link extraction module."""

import time
from pathlib import Path
from typing import List, Dict, Set, Optional
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.logger import get_logger, timed_operation, log_milestone
from utils.file_utils import save_links_to_file, save_json
from config.settings import get_config
from utils.seen_urls_manager import SeenUrlsManager
from scraper.selenium_utils import accept_cookies, scroll_page_for_lazy_content, wait_for_page_ready
from scraper.pagination import handle_pagination
from scraper.http_extractor import extract_links_from_http
from scraper.rss_extractor import RssExtractor

logger = get_logger(__name__)


@timed_operation("Chrome WebDriver initialization")
def create_webdriver() -> webdriver.Chrome:
    """
    Create and configure a Selenium WebDriver instance.
    
    Returns:
        Configured Chrome WebDriver
    """
    config = get_config()
    
    chrome_options = Options()
    
    if config.get('selenium.headless', True):
        chrome_options.add_argument('--headless')
    
    # Additional recommended options
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    
    # Use 'eager' page load strategy: stop waiting when DOM is interactive
    # This prevents timeout errors on sites with infinite-loading scripts
    chrome_options.page_load_strategy = 'eager'
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Set timeouts
    driver.implicitly_wait(config.get('selenium.implicit_wait', 15))
    driver.set_page_load_timeout(config.get('selenium.page_load_timeout', 30))
    
    logger.info("Created Chrome WebDriver")
    
    return driver

@timed_operation("Link extraction from page")
def extract_links_from_page(driver: webdriver.Chrome, base_url: str = "") -> Set[str]:
    """
    Extract all links from the current page (Selenium).
    Converts relative URLs to absolute.
    
    Args:
        driver: Selenium WebDriver instance
        base_url: Base URL for converting relative URLs to absolute
        
    Returns:
        Set of absolute URL strings
    """
    links = set()
    
    for a in driver.find_elements(By.TAG_NAME, 'a'):
        href = a.get_attribute('href')
        if href:
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            
            # Filter out anchors, mailto, javascript, etc
            if absolute_url.startswith(('http://', 'https://')):
                links.add(absolute_url)
    
    logger.debug(f"Extracted {len(links)} links from current page")
    
    return links
    return links


def scrape_site(driver: webdriver.Chrome, site_config: Dict) -> Set[str]:
    """
    Scrape all links from a single website.
    
    ROUTING LOGIC:
    - If site has rss_url configured: Use RSS extraction (fast, no Selenium)
    - Otherwise: Use existing Selenium/HTTP logic

    Args:
        driver: Selenium WebDriver instance
        site_config: Site configuration dictionary with keys:
            - name: Site name
            - url: Starting URL
            - rss_url: RSS feed URL (optional)
            - js: Whether JavaScript rendering is needed
            - next_selector: CSS selector for pagination (None if no pagination)
            - max_pages: Maximum pages to scrape
            - pagination_param: URL parameter to increment for pagination (optional)
            
    Returns:
        Set of all extracted URLs
    """
    config = get_config()
    
    name = site_config['name']
    url = site_config['url']
    rss_url = site_config.get('rss_url')

    # 1. RSS Path (No Selenium/HTTP needed)
    if rss_url:
        logger.info(f"🔔 Site '{name}' has RSS configured - using RSS extraction")
        try:
            return RssExtractor.scrape_site_rss(site_config)
        except Exception as e:
            logger.error(f"RSS extraction failed for '{name}', falling back to standard scraping: {e}")
            # Fall through to standard scraping if RSS fails
    
    # 2. Standard Selenium/HTTP Path (now used for EC sites too)
    js = site_config.get('js', None)  # None = auto-detect
    next_selector = site_config.get('next_selector')
    max_pages = site_config.get('max_pages', 1)
    pagination_param = site_config.get('pagination_param')
    
    logger.info(f"Scraping links from {name}: {url}")
    
    all_links = set()
    site_start_time = time.time()
    
    # Auto-detect JS requirement if not specified
    if js is None and max_pages == 1 and not next_selector:
        from scraper.http_extractor import detect_js_requirement
        
        logger.info(f"🔍 Auto-detecting JS requirement for {name}...")
        detection = detect_js_requirement(url, name)
        js = detection['needs_js']
        
        logger.info(f"  → Decision: {'⚡ JS NEEDED (Selenium)' if js else '🚀 NO JS (HTTP)'}")
        logger.info(f"  → Reason: {detection['reason']}")
    
    # Use HTTP for non-JS sites (MUCH faster!)
    if not js and max_pages == 1 and not next_selector:
        logger.info(f"🚀 Using fast HTTP method for {name}")
        all_links = extract_links_from_http(url, name)
        
        # If HTTP returns 0 links, force Selenium (content must be JS-rendered)
        if len(all_links) == 0:
            logger.warning(f"⚠️  HTTP returned 0 links, switching to Selenium for {name}")
            js = True
        else:
            total_elapsed = time.time() - site_start_time
            if all_links:
                avg_time_per_link = (total_elapsed / len(all_links)) * 1000
                log_milestone(f"Completed scraping {name}: {len(all_links)} links [HTTP]", total_elapsed, "✓")
                logger.debug(f"  Average {avg_time_per_link:.1f}ms per link extracted")
            return all_links
    
    # Use Selenium for JS sites or complex pagination
    logger.info(f"⚡ Using Selenium for {name} (JS/pagination required)")
    
    try:
        # Load the page
        page_start = time.time()
        driver.get(url)
        wait_for_page_ready(driver)
        page_elapsed = time.time() - page_start
        log_milestone(f"Loaded initial page for {name}", page_elapsed, "↓")
        
        # Wait for cookie banner and accept
        initial_wait = config.get('selenium.initial_wait', 2)
        time.sleep(initial_wait)
        accept_cookies(driver)
        
        page_count = 0
        last_url = driver.current_url
        
        # Pagination loop
        while True:
            # Accept cookies only on first page
            if page_count == 0:
                logger.debug(f"Attempting to accept cookies on first page...")
                cookie_accepted = accept_cookies(driver)
                if not cookie_accepted:
                    logger.debug(f"No cookie buttons found on first page")
            else:
                logger.debug(f"Skipping cookie acceptance on page {page_count + 1} (already handled)")
            
            # Wait for links to be present
            try:
                WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'a'))
                )
            except Exception as e:
                logger.debug(f"No links found for {name} after short wait: {e}")
                break
            
            # Scroll if JavaScript site
            if js:
                scroll_page_for_lazy_content(driver)
            
            # Extract links from current page
            links_before = set(all_links)
            page_links = extract_links_from_page(driver, url)
            all_links.update(page_links)
            
            new_links_count = len(all_links) - len(links_before)
            logger.info(f"Page {page_count + 1}: extracted {len(page_links)} links ({new_links_count} new)")
            
            # Check pagination
            page_count += 1
            
            # URL-based pagination
            if pagination_param and page_count < max_pages:
                try:
                    from scraper.pagination import increment_url_param
                    
                    current_page_num = page_count  # We're currently on page_count, next is page_count+1
                    new_url = increment_url_param(url, pagination_param, current_page_num)
                    
                    logger.info(f"Loading page {page_count + 1} via URL parameter: {new_url}")
                    driver.get(new_url)
                    
                    wait_for_page_ready(driver)
                    time.sleep(1)
                    
                    if js:
                        scroll_page_for_lazy_content(driver)
                    
                    url = new_url  # Update for next iteration
                    continue
                    
                except Exception as e:
                    logger.warning(f"Error loading page via URL parameter: {e}")
                    break
            
            # Button-based pagination
            if not next_selector or page_count >= max_pages:
                break
            
            # Handle pagination
            from scraper.pagination import click_next_button, detect_page_change
            
            clicked = click_next_button(driver, next_selector, name, page_count)
            
            if not clicked:
                break
            
            page_changed = detect_page_change(driver, last_url, links_before, js)
            
            if not page_changed:
                break
            
            last_url = driver.current_url
            time.sleep(1)
        
        total_elapsed = time.time() - site_start_time
        avg_time_per_link = (total_elapsed / len(all_links)) * 1000 if all_links else 0
        log_milestone(f"Completed scraping {name}: {len(all_links)} links from {page_count} pages [Selenium]", total_elapsed, "✓")
        logger.debug(f"  Average {avg_time_per_link:.1f}ms per link extracted")
        
    except Exception as e:
        logger.error(f"Error scraping {name}: {type(e).__name__}: {e}", exc_info=True)
    
    return all_links


def scrape_sites(
    sites: List[Dict],
    output_dir: Path,
    save_individual: bool = True,
    save_combined: bool = False,
    ignore_history: bool = False,
    rss_dir: Optional[Path] = None
) -> Dict[str, List[str]]:
    """
    Scrape multiple websites and save results.
    
    RSS sites are saved to rss_feeds/ directory with full metadata.
    Standard sites are saved to all_links/ directory as before.
    
    Args:
        sites: List of site configuration dictionaries
        output_dir: Directory to save output files
        save_individual: Whether to save individual files per site
        save_combined: Whether to save combined JSON
        ignore_history: If False (default), filters out URLs seen in previous runs
        rss_dir: Optional directory for RSS feeds (if None, uses config default)
        
    Returns:
        Dictionary mapping site names to lists of URLs
    """
    if not sites:
        logger.warning("No sites to scrape")
        return {}
    
    config = get_config()
    
    # Ensure output directories exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get RSS feeds directory (use provided or default from config)
    if rss_dir is None:
        rss_dir = config.get_full_path('paths.rss_feeds_dir')
    rss_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize SeenUrlsManager for cross-run deduplication
    seen_urls_manager = None
    if not ignore_history:
        seen_urls_manager = SeenUrlsManager()
        stats = seen_urls_manager.get_stats()
        logger.info(f"📚 Cross-run deduplication enabled: {stats['total_seen']} URLs in history")
    else:
        logger.info("🔓 Cross-run deduplication disabled: all URLs will be processed")
    
    results = {}
    driver = None
    total_filtered = 0  # Track total filtered URLs across all sites
    
    try:
        driver = create_webdriver()
        
        for site in sites:
            name = site['name']
            rss_url = site.get('rss_url')
            
            try:
                # RSS PATH: Extract with metadata and save separately
                if rss_url:
                    logger.info(f"🔔 Site '{name}' uses RSS - extracting with metadata")
                    
                    # Extract RSS metadata
                    rss_entries = RssExtractor.scrape_site_rss_with_metadata(site)
                    
                    # Extract URLs for backward compatibility
                    links = {entry['url'] for entry in rss_entries if 'url' in entry}
                    
                    # Filter out previously seen URLs
                    if seen_urls_manager:
                        original_count = len(links)
                        links = seen_urls_manager.filter_unseen_urls(links)
                        filtered = original_count - len(links)
                        total_filtered += filtered
                        if filtered > 0:
                            logger.info(f"  → Filtered {filtered} previously seen URLs for {name}")
                    
                    results[name] = sorted(list(links))
                    
                    if save_individual:
                        # Save RSS metadata to rss_feeds/ directory
                        rss_output_file = rss_dir / f"{name}_rss.json"
                        save_json(rss_entries, rss_output_file)
                        logger.info(f"  → Saved {len(rss_entries)} RSS entries with metadata to {rss_output_file}")
                        
                        # ALSO save standard links format for backward compatibility
                        output_file = output_dir / f"{name}_links.json"
                        links_json = {link: [] for link in links}
                        save_json(links_json, output_file)
                
                # STANDARD PATH: Use existing scrape_site logic
                else:
                    links = scrape_site(driver, site)
                    
                    # Filter out previously seen URLs
                    if seen_urls_manager:
                        original_count = len(links)
                        links = seen_urls_manager.filter_unseen_urls(links)
                        filtered = original_count - len(links)
                        total_filtered += filtered
                        if filtered > 0:
                            logger.info(f"  → Filtered {filtered} previously seen URLs for {name}")
                    
                    results[name] = sorted(list(links))
                    
                    # Save individual file in JSON format (no keywords)
                    if save_individual:
                        output_file = output_dir / f"{name}_links.json"
                        # Create dictionary mapping each link to empty array (keywords removed)
                        links_json = {
                            link: []
                            for link in links
                        }
                        save_json(links_json, output_file)
                
            except Exception as e:
                logger.error(f"Failed to scrape {name}: {e}", exc_info=True)
                results[name] = []
        
        # Save combined JSON
        if save_combined:
            combined_file = output_dir / "all_sites_links.json"
            save_json(results, combined_file)
        
        # Update seen URLs with new URLs
        if seen_urls_manager:
            all_new_urls = set()
            for site_urls in results.values():
                all_new_urls.update(site_urls)
            
            if all_new_urls:
                seen_urls_manager.mark_urls_as_seen(all_new_urls)
                seen_urls_manager.save_seen_urls()
                logger.info(f"📝 Added {len(all_new_urls)} new URLs to history")
            
            if total_filtered > 0:
                logger.info(f"🔍 Cross-run deduplication: filtered {total_filtered} previously seen URLs")
        
        logger.info(f"Scraping completed: {len(results)} sites processed")
        
    finally:
        if driver:
            driver.quit()
            logger.info("Closed WebDriver")
    
    return results
