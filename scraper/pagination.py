"""Pagination handling for web scraping."""

import time
import re
from typing import Optional, Set
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.logger import get_logger
from config.settings import get_config
from scraper.selenium_utils import hide_overlays, scroll_page_for_lazy_content

logger = get_logger(__name__)


def click_next_button(
    driver: WebDriver,
    selector: str,
    site_name: str,
    page_count: int,
    save_screenshots: bool = True
) -> bool:
    """
    Attempt to click the "next page" button using multiple strategies.
    
    Args:
        driver: Selenium WebDriver instance
        selector: CSS selector for the next button
        site_name: Name of site (for screenshot naming)
        page_count: Current page number (for screenshot naming)
        save_screenshots: Whether to save debugging screenshots
        
    Returns:
        True if button was clicked successfully, False otherwise
    """
    config = get_config()
    retries = config.get('scraping.pagination_retries', 3)
    
    hide_overlays(driver)
    
    try:
        next_btn = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        
        logger.debug(
            f"Next button found: tag={next_btn.tag_name}, text={next_btn.text}, "
            f"aria-disabled={next_btn.get_attribute('aria-disabled')}, "
            f"class={next_btn.get_attribute('class')}"
        )
        
        # Check if disabled
        if next_btn.get_attribute('aria-disabled') in ['true', 'True'] or next_btn.get_attribute('disabled'):
            logger.info(f"Next button is disabled for {site_name}, stopping pagination")
            return False
        
        # Scroll to element
        driver.execute_script("arguments[0].scrollIntoView();", next_btn)
        hide_overlays(driver)
        
    except Exception as e:
        logger.warning(f"Could not find next button: {e}")
        return False
    
    # Try multiple click strategies
    clicked = False
    
    for attempt in range(retries):
        try:
            # Re-find element to avoid stale reference
            fresh_btn = driver.find_element(By.CSS_SELECTOR, selector)
            
            logger.debug(f"Attempt {attempt + 1} - Button info:")
            logger.debug(f"  - Tag: {fresh_btn.tag_name}")
            logger.debug(f"  - Text: '{fresh_btn.text}'")
            logger.debug(f"  - Displayed: {fresh_btn.is_displayed()}")
            logger.debug(f"  - Enabled: {fresh_btn.is_enabled()}")
            
            # Get element position
            location = fresh_btn.location
            size = fresh_btn.size
            x = location['x'] + size['width'] // 2
            y = location['y'] + size['height'] // 2
            
            # Strategy 1: JavaScript click (most reliable)
            try:
                logger.debug(f"Attempting JS click...")
                
                if save_screenshots and config.get('selenium.screenshot_on_error', True):
                    try:
                        driver.save_screenshot(f"before_click_{site_name}_page_{page_count}_attempt_{attempt}.png")
                    except:
                        pass
                
                url_before_click = driver.current_url
                
                driver.execute_script("arguments[0].click();", fresh_btn)
                time.sleep(1)
                
                url_after_click = driver.current_url
                
                if url_after_click != url_before_click:
                    logger.info(f"✓ URL changed after JS click!")
                
                if save_screenshots and config.get('selenium.screenshot_on_error', True):
                    try:
                        driver.save_screenshot(f"after_click_{site_name}_page_{page_count}_attempt_{attempt}.png")
                    except:
                        pass
                
                clicked = True
                logger.info(f"Successfully executed JavaScript click on attempt {attempt + 1}")
                break
                
            except Exception as js_ex:
                logger.debug(f"JS click failed on attempt {attempt + 1}: {type(js_ex).__name__}: {js_ex}")
            
            # Strategy 2: Click at coordinates
            try:
                logger.debug(f"Attempting coordinate click at ({x}, {y})...")
                driver.execute_script(f"document.elementFromPoint({x}, {y}).click();")
                time.sleep(1)
                
                clicked = True
                logger.info(f"Successfully clicked using coordinates on attempt {attempt + 1}")
                break
                
            except Exception as coord_ex:
                logger.debug(f"Coordinate click failed on attempt {attempt + 1}: {type(coord_ex).__name__}: {coord_ex}")
            
            # Strategy 3: Click parent element
            try:
                logger.debug(f"Attempting to click parent element...")
                parent = fresh_btn.find_element(By.XPATH, "..")
                driver.execute_script("arguments[0].click();", parent)
                time.sleep(1)
                
                clicked = True
                logger.info(f"Successfully clicked parent element on attempt {attempt + 1}")
                break
                
            except Exception as parent_ex:
                logger.debug(f"Parent click failed on attempt {attempt + 1}: {type(parent_ex).__name__}: {parent_ex}")
                
        except Exception as find_ex:
            logger.debug(f"Could not find element on attempt {attempt + 1}: {type(find_ex).__name__}: {find_ex}")
            
            if attempt < retries - 1:
                time.sleep(1)
                hide_overlays(driver)
    
    if not clicked:
        logger.error(f"Could not click next button for {site_name} after {retries} attempts")
    
    return clicked


def detect_page_change(
    driver: WebDriver,
    last_url: str,
    previous_links: Set[str],
    js_mode: bool = False
) -> bool:
    """
    Detect if page has changed after pagination click.
    
    Uses multiple methods:
    1. URL change detection
    2. New links detection (for AJAX-based pagination)
    
    Args:
        driver: Selenium WebDriver instance
        last_url: URL before pagination
        previous_links: Set of links from previous page
        js_mode: Whether to use extended scrolling for JS sites
        
    Returns:
        True if page changed, False otherwise
    """
    config = get_config()
    timeout = config.get('scraping.page_change_timeout', 8)
    extended_wait = config.get('scraping.extended_wait', 5)
    
    logger.debug(f"Current URL before waiting: {driver.current_url}")
    logger.info("Waiting for page to change...")
    
    page_changed = False
    
    # Method 1: Wait for URL change
    try:
        for i in range(timeout * 2):  # Check every 0.5 seconds
            time.sleep(0.5)
            current_url = driver.current_url
            
            if i % 4 == 0:  # Log every 2 seconds
                logger.debug(f"URL check {i//2 + 1}/{timeout}: {current_url}")
            
            if current_url != last_url:
                page_changed = True
                logger.info(f"Page changed - URL updated from {last_url} to {current_url}")
                break
        
        if not page_changed:
            logger.warning(f"URL still unchanged after {timeout} seconds: {driver.current_url}")
            
    except Exception as url_ex:
        logger.error(f"Error checking URL: {url_ex}")
    
    # Method 2: If URL didn't change, check for new content
    if not page_changed:
        try:
            logger.info("Waiting longer for content to fully load...")
            time.sleep(extended_wait)
            
            # Scroll if JS mode
            if js_mode:
                logger.info("Force scrolling to load lazy content...")
                scroll_page_for_lazy_content(driver, max_iterations=15)
            
            # Check for new links
            current_links = set()
            for a in driver.find_elements(By.TAG_NAME, 'a'):
                href = a.get_attribute('href')
                if href:
                    current_links.add(href)
            
            new_links = current_links - previous_links
            
            logger.debug(f"Links before: {len(previous_links)}, current: {len(current_links)}, new: {len(new_links)}")
            
            if new_links:
                page_changed = True
                logger.info(f"Page changed - found {len(new_links)} new unique links after extended loading")
                # Sample new links for debugging
                sample_new = list(new_links)[:3]
                logger.debug(f"Sample new links: {sample_new}")
            else:
                logger.info("No new unique links detected")
                
        except Exception as content_check_ex:
            logger.warning(f"Could not check for new content: {type(content_check_ex).__name__}: {content_check_ex}")
    
    return page_changed


def increment_url_param(url: str, param_name: str, current_value: int) -> str:
    """
    Increment a URL parameter value.
    
    Args:
        url: The URL to modify
        param_name: Name of the parameter to increment
        current_value: Current value of the parameter
        
    Returns:
        Updated URL with incremented parameter
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    
    # Update parameter
    params[param_name] = [str(current_value + 1)]
    
    # Rebuild query string
    new_query = urlencode(params, doseq=True)
    
    # Rebuild URL
    new_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    
    return new_url


def handle_pagination(
    driver: WebDriver,
    site_name: str,
    next_selector: Optional[str],
    max_pages: int,
    links: Set[str],
    js_mode: bool = False,
    pagination_param: Optional[str] = None,
    base_url: Optional[str] = None
) -> Set[str]:
    """
    Handle pagination for a website.
    
    Args:
        driver: Selenium WebDriver instance
        site_name: Name of the site being scraped
        next_selector: CSS selector for next button (None if no pagination)
        max_pages: Maximum pages to scrape
        links: Set of links collected so far
        js_mode: Whether site uses JavaScript rendering
        pagination_param: URL parameter to increment for pagination (e.g., "pageNumber", "page")
        base_url: Base URL with pagination parameter (used with pagination_param)
        
    Returns:
        Updated set of links after pagination
    """
    # URL-based pagination
    if pagination_param and base_url and max_pages > 1:
        logger.info(f"Starting URL-based pagination for {site_name} using parameter '{pagination_param}' (max {max_pages} pages)")
        
        # Extract initial page number from base_url
        parsed = urlparse(base_url)
        params = parse_qs(parsed.query)
        current_page = int(params.get(pagination_param, [1])[0])
        
        for page_num in range(current_page + 1, current_page + max_pages):
            try:
                new_url = increment_url_param(base_url, pagination_param, page_num - 1)
                logger.info(f"Navigating to page {page_num}: {new_url}")
                
                driver.get(new_url)
                time.sleep(3)
                
                if js_mode:
                    scroll_page_for_lazy_content(driver)
                
                # Extract links will be done by caller
                logger.info(f"Successfully loaded page {page_num}")
                base_url = new_url  # Update for next iteration
                
            except Exception as e:
                logger.warning(f"Error loading page {page_num}: {e}")
                break
        
        logger.info(f"Completed URL-based pagination for {site_name}")
        return links
    
    # Button-based pagination
    if not next_selector or max_pages <= 1:
        return links
    
    logger.info(f"Starting button-based pagination for {site_name} (max {max_pages} pages)")
    
    page_count = 1
    last_url = driver.current_url
    
    while page_count < max_pages:
        previous_links = set(links)
        
        # Try to click next button
        clicked = click_next_button(driver, next_selector, site_name, page_count)
        
        if not clicked:
            logger.info(f"No more pages for {site_name}")
            break
        
        # Detect page change
        page_changed = detect_page_change(driver, last_url, previous_links, js_mode)
        
        if not page_changed:
            logger.info("No page change detected, stopping pagination")
            break
        
        last_url = driver.current_url
        page_count += 1
        
        # Extract links from new page (will be done by caller)
        logger.info(f"Successfully navigated to page {page_count} for {site_name}")
        
        time.sleep(2)
    
    logger.info(f"Completed pagination for {site_name}: {page_count} pages scraped")
    
    return links
