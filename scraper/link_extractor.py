"""Main link extraction module."""

import time
from pathlib import Path
from typing import List, Dict, Set
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.logger import get_logger
from utils.file_utils import save_links_to_file, save_json
from config.settings import get_config
from scraper.selenium_utils import accept_cookies, scroll_page_for_lazy_content, wait_for_page_ready
from scraper.pagination import handle_pagination

logger = get_logger(__name__)


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
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Set timeouts
    driver.implicitly_wait(config.get('selenium.implicit_wait', 15))
    driver.set_page_load_timeout(config.get('selenium.page_load_timeout', 30))
    
    logger.info("Created Chrome WebDriver")
    
    return driver


def extract_links_from_page(driver: webdriver.Chrome) -> Set[str]:
    """
    Extract all links from the current page.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        Set of URL strings
    """
    links = set()
    
    for a in driver.find_elements(By.TAG_NAME, 'a'):
        href = a.get_attribute('href')
        if href:
            links.add(href)
    
    logger.debug(f"Extracted {len(links)} links from current page")
    
    return links


def scrape_site(driver: webdriver.Chrome, site_config: Dict) -> Set[str]:
    """
    Scrape all links from a single website.
    
    Args:
        driver: Selenium WebDriver instance
        site_config: Site configuration dictionary with keys:
            - name: Site name
            - url: Starting URL
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
    js = site_config.get('js', False)
    next_selector = site_config.get('next_selector')
    max_pages = site_config.get('max_pages', 1)
    pagination_param = site_config.get('pagination_param')
    
    logger.info(f"Scraping links from {name}: {url}")
    
    all_links = set()
    
    try:
        # Load the page
        driver.get(url)
        
        # Wait for page to be ready
        wait_for_page_ready(driver)
        
        # Wait for cookie banner and accept
        initial_wait = config.get('selenium.initial_wait', 2)
        time.sleep(initial_wait)
        accept_cookies(driver)
        
        page_count = 0
        last_url = driver.current_url
        
        # Pagination loop
        while True:
            # Accept cookies on each page (in case they reappear)
            logger.debug(f"Attempting to accept cookies on page {page_count + 1}...")
            cookie_accepted = accept_cookies(driver)
            
            if not cookie_accepted:
                logger.debug(f"No cookie buttons found on page {page_count + 1}")
            
            # Wait for links to be present
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'a'))
                )
            except Exception as e:
                logger.warning(f"No links found for {name} after waiting: {e}")
                break
            
            # Scroll if JavaScript site
            if js:
                scroll_page_for_lazy_content(driver)
            
            # Extract links from current page
            links_before = set(all_links)
            page_links = extract_links_from_page(driver)
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
                    time.sleep(2)
                    
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
            time.sleep(2)
        
        logger.info(f"Completed scraping {name}: {len(all_links)} total links from {page_count} pages")
        
    except Exception as e:
        logger.error(f"Error scraping {name}: {type(e).__name__}: {e}", exc_info=True)
    
    return all_links


def scrape_sites(
    sites: List[Dict],
    output_dir: Path,
    save_individual: bool = True,
    save_combined: bool = False
) -> Dict[str, List[str]]:
    """
    Scrape multiple websites and save results.
    
    Args:
        sites: List of site configuration dictionaries
        output_dir: Directory to save output files
        save_individual: Whether to save individual files per site
        save_combined: Whether to save combined JSON
        
    Returns:
        Dictionary mapping site names to lists of URLs
    """
    if not sites:
        logger.warning("No sites to scrape")
        return {}
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    driver = None
    
    try:
        driver = create_webdriver()
        
        for site in sites:
            name = site['name']
            
            try:
                links = scrape_site(driver, site)
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
        
        logger.info(f"Scraping completed: {len(results)} sites processed")
        
    finally:
        if driver:
            driver.quit()
            logger.info("Closed WebDriver")
    
    return results
