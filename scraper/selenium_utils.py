"""Selenium utility functions for web scraping."""

import time
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from utils.logger import get_logger, timed_operation
from config.settings import get_config

logger = get_logger(__name__)


@timed_operation("Cookie acceptance")
def accept_cookies(driver: WebDriver) -> bool:
    """
    Attempt to accept cookies on a webpage using multiple strategies.
    
    This function tries to find and click cookie consent buttons using:
    1. Attribute-based CSS selectors (id, class, data-testid, aria-label)
    2. Text-based searches (case insensitive)
    3. JavaScript click as fallback when direct click fails
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        True if cookie button was found and clicked, False otherwise
    """
    config = get_config()
    
    logger.debug("Looking for cookie banners...")
    
    # Get configuration
    text_patterns = config.get('cookies.text_patterns', [])
    attribute_selectors = config.get('cookies.attribute_selectors', [])
    cookie_wait = config.get('selenium.cookie_wait', 1)
    
    # Strategy 1: Try attribute-based selectors first (faster)
    for selector in attribute_selectors:
        try:
            cookie_btn = driver.find_element(By.CSS_SELECTOR, selector)
            if cookie_btn.is_displayed() and cookie_btn.is_enabled():
                logger.debug(f"Found cookie button with selector: {selector}")
                logger.debug(f"Button text: '{cookie_btn.text[:100]}'")
                
                try:
                    cookie_btn.click()
                    logger.info(f"✓ Accepted cookies using attribute selector: {selector}")
                    time.sleep(cookie_wait)
                    return True
                except Exception as click_ex:
                    logger.debug(f"Direct click failed: {click_ex}")
                    
                    try:
                        # Fallback to JavaScript click
                        driver.execute_script("arguments[0].click();", cookie_btn)
                        logger.info(f"✓ Accepted cookies using JS click (attribute): {selector}")
                        time.sleep(cookie_wait)
                        return True
                    except Exception as js_ex:
                        logger.debug(f"JS click also failed: {js_ex}")
        except:
            continue
    
    # Strategy 2: Try text-based search (more flexible but slower)
    for pattern in text_patterns:
        try:
            # XPath to find buttons/links with text containing pattern (case insensitive)
            xpath = (
                f"//button[contains(translate(normalize-space(text()), "
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{pattern.lower()}')] | "
                f"//a[contains(translate(normalize-space(text()), "
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{pattern.lower()}')]"
            )
            
            cookie_buttons = driver.find_elements(By.XPATH, xpath)
            
            for cookie_btn in cookie_buttons:
                if cookie_btn.is_displayed() and cookie_btn.is_enabled():
                    logger.debug(f"Found cookie button with text pattern '{pattern}': '{cookie_btn.text[:100]}'")
                    
                    try:
                        cookie_btn.click()
                        logger.info(f"✓ Accepted cookies using text pattern '{pattern}': {cookie_btn.text[:50]}")
                        time.sleep(cookie_wait)
                        return True
                    except Exception as click_ex:
                        logger.debug(f"Direct click failed: {click_ex}")
                        
                        try:
                            # Fallback to JavaScript click
                            driver.execute_script("arguments[0].click();", cookie_btn)
                            logger.info(f"✓ Accepted cookies using JS click (text pattern '{pattern}'): {cookie_btn.text[:50]}")
                            time.sleep(cookie_wait)
                            return True
                        except Exception as js_ex:
                            logger.debug(f"JS click also failed: {js_ex}")
                            continue
                            
        except Exception as pattern_ex:
            logger.debug(f"Error with pattern '{pattern}': {pattern_ex}")
            continue
    
    logger.debug("No cookie buttons found or clickable")
    return False


def hide_overlays(driver: WebDriver) -> None:
    """
    Hide common page overlays that might intercept clicks.
    
    This function uses JavaScript to hide elements like language selectors,
    toolbars, modals, and other overlays that could prevent interaction
    with page elements.
    
    Args:
        driver: Selenium WebDriver instance
    """
    config = get_config()
    selectors = config.get('overlays.selectors', [])
    
    try:
        # Build JavaScript selector list
        js_selectors = ', '.join([f"'{s}'" for s in selectors])
        
        driver.execute_script(f"""
            const selectors = [{js_selectors}];
            selectors.forEach(selector => {{
                document.querySelectorAll(selector).forEach(el => {{
                    el.style.display = 'none';
                    el.style.visibility = 'hidden';
                    el.style.zIndex = '-9999';
                }});
            }});
        """)
        
        time.sleep(0.5)
        logger.debug("Hidden page overlays")
        
    except Exception as e:
        logger.debug(f"Error hiding overlays: {e}")


def scroll_page_for_lazy_content(driver: WebDriver, max_iterations: Optional[int] = None) -> None:
    """
    Scroll page to load lazy-loaded content.
    
    Repeatedly scrolls to bottom of page until no more content loads.
    Useful for pages with infinite scroll or lazy-loaded content.
    
    Args:
        driver: Selenium WebDriver instance
        max_iterations: Maximum scroll iterations (uses config default if None)
    """
    config = get_config()
    
    if max_iterations is None:
        max_iterations = config.get('scraping.scroll_iterations', 50)
    
    max_iterations = int(max_iterations) if max_iterations is not None else 50
    scroll_delay = config.get('scraping.scroll_delay', 1.5)
    
    scroll_start = time.time()
    logger.debug(f"Scrolling page for lazy content (max {max_iterations} iterations)")
    
    last_height = driver.execute_script("return document.body.scrollHeight")
    initial_height = last_height
    
    for i in range(max_iterations):
        # Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_delay)
        
        # Check if height changed
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        if new_height == last_height:
            scroll_elapsed = time.time() - scroll_start
            height_delta = new_height - initial_height
            logger.debug(f"  Height stabilized after {i + 1} scrolls ({scroll_elapsed:.1f}s, delta: {height_delta}px)")
            break
        
        last_height = new_height
    else:
        # Loop completed without break
        scroll_elapsed = time.time() - scroll_start
        height_delta = last_height - initial_height
        logger.debug(f"  Reached max iterations ({max_iterations}), delta: {height_delta}px")


def click_tabs_and_expandable_elements(driver: WebDriver) -> int:
    """
    Click tabs, 'show more' buttons, accordion items, and other expandable elements.
    
    This function identifies and clicks interactive UI elements that may hide content
    (tabs, accordions, "show more" buttons, etc.), allowing lazy-loaded content to be
    rendered before extraction.
    
    Args:
        driver: Selenium WebDriver instance
        
    Returns:
        Number of elements clicked
    """
    config = get_config()
    
    # CSS selectors and text patterns for expandable elements
    expandable_selectors = [
        # Tab buttons
        '[role="tab"]',
        '[role="tab"][aria-selected="false"]',
        'button[aria-controls*="panel"]',
        'button[aria-expanded="false"]',
        # Show more / Load more buttons
        'button:contains("Show more")',
        'button:contains("show more")',
        'button:contains("Load more")',
        'button:contains("load more")',
        'button:contains("Show more grants")',
        'a:contains("Show more")',
        'a:contains("show more")',
        # Accordion headers
        '.accordion-header',
        '[role="button"][aria-expanded="false"]',
        # Generic expandable patterns
        'button[class*="expand"]',
        'button[class*="collapse"]',
        'button[class*="toggle"]',
    ]
    
    # Text patterns to search for in buttons/links
    text_patterns = [
        'show more',
        'show details',
        'read more',
        'load more',
        'expand',
        'leggi di più',
        'mostra di più',
        'visualizza più',
        'ulteriori dettagli',
        'details',
        'more info',
    ]
    
    clicked_count = 0
    click_delay = config.get('scraping.scroll_delay', 0.3)
    max_clicks = config.get('scraping.max_expandable_clicks', 30)
    
    logger.debug(f"Clicking expandable elements (max {max_clicks} clicks)")
    
    try:
        # Strategy 1: Click by XPath looking for text patterns
        for pattern in text_patterns:
            if clicked_count >= max_clicks:
                break
            
            try:
                # Case-insensitive text search for buttons and links
                xpath = (
                    f"//button[contains(translate(normalize-space(text()), "
                    f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{pattern.lower()}')] | "
                    f"//a[contains(translate(normalize-space(text()), "
                    f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{pattern.lower()}')]"
                )
                
                elements = driver.find_elements(By.XPATH, xpath)
                
                for elem in elements:
                    if clicked_count >= max_clicks:
                        break
                    
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            # Scroll into view
                            driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                            time.sleep(click_delay / 2)
                            
                            # Try regular click
                            try:
                                elem.click()
                                logger.debug(f"Clicked '{pattern}' button: {elem.text[:50]}")
                                clicked_count += 1
                                time.sleep(click_delay)
                            except:
                                # Fallback to JS click
                                driver.execute_script("arguments[0].click();", elem)
                                logger.debug(f"JS-clicked '{pattern}' button: {elem.text[:50]}")
                                clicked_count += 1
                                time.sleep(click_delay)
                    except Exception as e:
                        logger.debug(f"Could not click element: {e}")
                        continue
            
            except Exception as e:
                logger.debug(f"Error searching for pattern '{pattern}': {e}")
                continue
        
        # Strategy 2: Click tab elements that are not selected
        if clicked_count < max_clicks:
            try:
                tabs = driver.find_elements(By.CSS_SELECTOR, '[role="tab"][aria-selected="false"]')
                for tab in tabs:
                    if clicked_count >= max_clicks:
                        break
                    
                    try:
                        driver.execute_script("arguments[0].scrollIntoView(true);", tab)
                        time.sleep(click_delay / 2)
                        
                        try:
                            tab.click()
                        except:
                            driver.execute_script("arguments[0].click();", tab)
                        
                        logger.debug(f"Clicked unselected tab: {tab.text[:50]}")
                        clicked_count += 1
                        time.sleep(click_delay)
                    except Exception as e:
                        logger.debug(f"Could not click tab: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Error clicking tabs: {e}")
        
        # Strategy 3: Click collapsed accordion/details elements
        if clicked_count < max_clicks:
            try:
                collapsed = driver.find_elements(By.CSS_SELECTOR, '[role="button"][aria-expanded="false"]')
                for elem in collapsed:
                    if clicked_count >= max_clicks:
                        break
                    
                    try:
                        driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                        time.sleep(click_delay / 2)
                        
                        try:
                            elem.click()
                        except:
                            driver.execute_script("arguments[0].click();", elem)
                        
                        logger.debug(f"Clicked collapsed element")
                        clicked_count += 1
                        time.sleep(click_delay)
                    except Exception as e:
                        logger.debug(f"Could not click collapsed element: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Error clicking collapsed elements: {e}")
        
        if clicked_count > 0:
            logger.info(f"✓ Clicked {clicked_count} expandable elements")
            # Final scroll to load any remaining content
            time.sleep(0.5)
            scroll_page_for_lazy_content(driver, max_iterations=3)
    
    except Exception as e:
        logger.error(f"Error in click_tabs_and_expandable_elements: {e}")
    
    return clicked_count


@timed_operation("Page readiness wait")
def wait_for_page_ready(driver: WebDriver, timeout: int = 15) -> bool:
    """
    Wait for page to be ready (document ready state complete).
    
    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if page is ready, False if timeout
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        ready_state = driver.execute_script("return document.readyState")
        
        if ready_state == "complete":
            logger.debug("Page ready")
            return True
        
        time.sleep(0.1)
    
    logger.debug(f"Page not fully ready, proceeding anyway")
    return False
