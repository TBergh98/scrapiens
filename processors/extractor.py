"""Grant details extraction module using GPT-4o and Selenium."""

import time
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from dateutil import parser as date_parser
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import OpenAI, RateLimitError, APIError
from utils.logger import get_logger
from config.settings import get_config
from scraper.selenium_utils import click_tabs_and_expandable_elements
from processors.site_profiles import SiteProfileManager

logger = get_logger(__name__)


def preprocess_ec_europa_html(html_content: str, url: str) -> Optional[str]:
    """
    Preprocess EC Europa HTML to extract only relevant cards/sections, removing noise.
    
    Returns clean HTML containing only the 3 main cards (for CALL) or sections (for TENDER),
    suitable for GPT extraction. Reduces HTML size from ~15KB to ~4-5KB.
    
    This function handles two templates:
    - CALL template (topic-details): Extracts 3 cards:
      * General information card
      * Topic description card  
      * Topic conditions and documents card
    - TENDER template (tender-details): Extracts General information card
    
    Args:
        html_content: Raw HTML from the page
        url: URL of the page (for template detection)
        
    Returns:
        Cleaned HTML string with only relevant cards, or None if preprocessing fails
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        logger.info(f"🔍 Preprocessing EC Europa HTML for: {url}")
        
        # Detect template type
        is_call_template = 'topic-details' in url.lower()
        is_tender_template = 'tender-details' in url.lower()
        
        cards_html = []
        
        if is_call_template:
            # ===== CALL TEMPLATE: Extract 3 main cards =====
            card_titles = [
                'General information',
                'Topic description',
                'Topic conditions and documents'
            ]
            
            for title in card_titles:
                header = soup.find('eui-card-header-title', string=title)
                if header:
                    card = header.find_parent('eui-card')
                    if card:
                        cards_html.append(str(card))
                        logger.debug(f"  ✓ Extracted {title} card")
                    else:
                        logger.debug(f"  ⚠ Could not find parent card for {title}")
                else:
                    logger.debug(f"  ⚠ Could not find header for {title}")
        
        elif is_tender_template:
            # ===== TENDER TEMPLATE: Extract General information card =====
            header = soup.find('eui-card-header-title', string='General information')
            if header:
                card = header.find_parent('eui-card')
                if card:
                    cards_html.append(str(card))
                    logger.debug(f"  ✓ Extracted General information card")
                else:
                    logger.warning("⚠ Could not find parent card for General information")
            else:
                logger.warning("⚠ Could not find General information card header")
        
        if not cards_html:
            logger.warning("⚠ EC Europa preprocessing: No relevant cards found")
            return None
        
        # Combine all cards into a single HTML document
        preprocessed_html = '<div>' + ''.join(cards_html) + '</div>'
        
        logger.info(f"✅ EC Europa preprocessing successful: {len(preprocessed_html)} chars (reduced from {len(html_content)} chars)")
        return preprocessed_html
        
    except Exception as e:
        logger.error(f"❌ EC Europa preprocessing failed: {e}")
        return None


def extract_deadline_with_regex(html_content: str) -> Optional[str]:
    """
    Fallback function to extract deadline using regex patterns.
    
    Tries multiple regex patterns to find dates in common deadline formats.
    Used when GPT extraction fails or returns null.
    
    Args:
        html_content: HTML content to search
        
    Returns:
        Deadline in YYYY-MM-DD format, or None if not found
    """
    
    # Remove HTML tags and decode entities for cleaner text
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    
    # Patterns to search for deadline-related text (case insensitive)
    deadline_prefixes = [
        r'scadenza[:\s]*',
        r'deadline[:\s]*',
        r'data limite[:\s]*',
        r'application deadline[:\s]*',
        r'closing date[:\s]*',
        r'application closes[:\s]*',
        r'ends on[:\s]*',
        r'data di chiusura[:\s]*',
        r'data di scadenza[:\s]*',
        r'ultimo giorno[:\s]*',
        r'last day[:\s]*',
    ]
    
    # Date patterns (multiple formats)
    date_patterns = [
        # DD/MM/YYYY or DD-MM-YYYY
        r'(?:0?[1-9]|[12][0-9]|3[01])[/-](?:0?[1-9]|1[012])[/-](20\d{2})',
        # YYYY-MM-DD or YYYY/MM/DD
        r'(20\d{2})[/-](?:0?[1-9]|1[012])[/-](?:0?[1-9]|[12][0-9]|3[01])',
        # Month names: 31 December 2024, Dec 31 2024, etc.
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December|'
        r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|'
        r'Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|Settembre|Ottobre|Novembre|Dicembre)\s+(\d{1,2}),?\s+(20\d{2})',
    ]
    
    # Search for deadline with prefix
    for prefix in deadline_prefixes:
        # Look for the pattern within ~200 chars after the prefix
        match = re.search(
            prefix + r'[^\n]*?(' + '|'.join(date_patterns) + ')',
            text,
            re.IGNORECASE | re.DOTALL
        )
        
        if match:
            date_str = match.group(0).split(prefix)[1].strip()
            
            try:
                # Try to parse the date
                parsed = date_parser.parse(date_str, dayfirst=True)
                
                # Only accept dates in the future (or current year)
                if parsed.year >= datetime.now().year - 1:
                    logger.debug(f"Extracted deadline via regex: {parsed.strftime('%Y-%m-%d')}")
                    return parsed.strftime('%Y-%m-%d')
            except:
                continue
    
    logger.debug("No deadline found via regex patterns")
    return None


class GrantExtractor:
    """Extracts detailed information from research grant pages using GPT-4o."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the grant extractor.
        
        Args:
            api_key: OpenAI API key (uses config if None)
            model: Model name (uses config if None)
        """
        config = get_config()
        
        self.api_key = api_key or config.openai_api_key
        self.model = model or config.get('extractor.model', 'gpt-4o')
        self.timeout = config.get('extractor.timeout', 10)
        self.max_retries = config.get('extractor.max_retries', 3)
        self.parallel_workers = config.get('extractor.parallel_workers', 10)
        
        self.client = OpenAI(api_key=self.api_key)
        self.site_profiles = SiteProfileManager()
        
        logger.info(f"Initialized GrantExtractor with model: {self.model}")
    
    def _create_driver(self, url: str) -> webdriver.Chrome:
        """Create a Selenium WebDriver instance for extraction."""
        config = get_config()
        
        # Get recommended settings based on site profile
        recommended = self.site_profiles.get_recommended_settings(url)
        timeout = recommended.get('page_load_timeout', config.get('selenium.page_load_timeout', 8))
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(5)
        driver.set_page_load_timeout(timeout)
        
        return driver
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        reraise=True
    )
    def _extract_with_gpt(self, html_content: str, url: str) -> Dict[str, Any]:
        """
        Extract grant details from HTML using GPT-4o.
        
        Args:
            html_content: HTML content of the grant page
            url: URL of the page (for context)
            
        Returns:
            Dictionary with extracted grant details
        """
        config = get_config()
        
        # Get prompt from config.yaml - this is the ONLY source of truth
        # The config prompt includes the critical 'is_grant' field that validates if page is a grant
        prompt_template = config.get('extractor.extraction_prompt')
        
        if not prompt_template:
            raise ValueError(
                "Missing 'extractor.extraction_prompt' in config.yaml. "
                "This prompt is required and must include 'is_grant' validation field."
            )
        
        # Truncate HTML to avoid token limits
        html_truncated = html_content[:15000]
        
        # Avoid str.format here because the prompt contains literal JSON braces; simple replaces prevent KeyError
        prompt = (
            prompt_template
            .replace("{url}", url)
            .replace("{html}", html_truncated)
        )
        
        logger.debug(f"Sending extraction request for: {url}")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at extracting structured information from HTML pages. You respond with valid JSON only. Never invent information that is not present in the source."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,  # Low temperature for factual extraction
            timeout=60
        )
        
        response_text = response.choices[0].message.content
        
        if response_text is None:
            raise ValueError("API response content is None")
        
        # Extract JSON from response
        if '```json' in response_text:
            json_start = response_text.find('```json') + 7
            json_end = response_text.find('```', json_start)
            response_text = response_text[json_start:json_end].strip()
        elif '```' in response_text:
            json_start = response_text.find('```') + 3
            json_end = response_text.find('```', json_start)
            response_text = response_text[json_start:json_end].strip()
        
        # Log raw response for debugging malformed JSON issues
        logger.debug(f"Raw GPT response (first 500 chars): {response_text[:500]}")
        
        try:
            result = json.loads(response_text)
            
            # Fix malformed JSON with escaped quotes in keys (e.g., "\"is_grant\"" instead of "is_grant")
            # This can happen when GPT returns doubly-encoded JSON
            if isinstance(result, dict):
                fixed_result = {}
                for key, value in result.items():
                    try:
                        # Remove quotes from key if present
                        clean_key = key.strip('"\'')
                        fixed_result[clean_key] = value
                    except Exception as e:
                        # If key cleaning fails for any reason, keep original key
                        logger.warning(f"Failed to clean key '{key}': {e}. Using original key.")
                        fixed_result[key] = value
                result = fixed_result
                
            logger.debug(f"Parsed result keys: {list(result.keys())}")
            logger.debug(f"Result dict content: {result}")
            
            # Verify result is a dict before proceeding
            if not isinstance(result, dict):
                raise ValueError(f"Expected dict from GPT, got {type(result)}: {result}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from GPT response: {e}")
            logger.debug(f"Raw response: {response_text}")
            raise ValueError(f"Invalid JSON from GPT: {str(e)}")
        
        # Helper function to get value with fallback for malformed keys
        def safe_get(d, key, default=None):
            """Get value from dict, trying multiple key variants."""
            if not isinstance(d, dict):
                logger.error(f"safe_get called with non-dict: {type(d)}")
                return default
                
            # Try exact key
            if key in d:
                return d[key]
            # Try with quotes
            quoted_key = f'"{key}"'
            if quoted_key in d:
                return d[quoted_key]
            # Try with single quotes
            single_quoted = f"'{key}'"
            if single_quoted in d:
                return d[single_quoted]

            # Log all available keys when key not found
            logger.warning(f"Key '{key}' not found. Available keys: {list(d.keys())}")
            return default
        
        # Handle non-grant pages (is_grant: false)
        # Use safe_get to handle various key formats
        try:
            is_grant = safe_get(result, 'is_grant', True)
            logger.debug(f"is_grant value: {is_grant} (type: {type(is_grant)})")
        except Exception as e:
            logger.error(f"Error getting is_grant from result: {e}")
            logger.error(f"Result type: {type(result)}, Result: {result}")
            raise
        
        if not is_grant:
            invalid_reason = safe_get(result, 'invalid_reason', 'Unknown reason')
            logger.info(f"Page is not a grant: {invalid_reason}")
            return {
                'is_grant': False,
                'invalid_reason': invalid_reason,
                'title': None,
                'organization': None,
                'abstract': None,
                'deadline': None,
                'funding_amount': None
            }
        
        # Validate and normalize deadline format
        if result.get('deadline'):
            try:
                # Parse date with dateutil for flexibility
                parsed_date = date_parser.parse(str(result['deadline']))
                result['deadline'] = parsed_date.strftime('%Y-%m-%d')
            except Exception as e:
                logger.warning(f"Could not parse deadline '{result['deadline']}': {e}")
                result['deadline'] = None
        
        return result
    
    def _is_ec_europa_special_url(self, url: str) -> bool:
        """
        Helper function to identify EC Europa special URLs that require aggressive extraction.
        
        Identifies URLs from ec.europa.eu that contain 'tender-details' or 'topic-details'
        path segments, which require special handling due to their complex JavaScript-heavy
        page structure.
        
        Args:
            url: The URL to check
            
        Returns:
            True if URL is from ec.europa.eu with tender-details or topic-details, False otherwise
        """
        if not url:
            return False
        
        # Check if URL is from ec.europa.eu domain
        is_ec_europa = 'ec.europa.eu' in url.lower()
        
        # Check for special path segments that require aggressive extraction
        has_special_path = (
            'tender-details' in url.lower() or 
            'topic-details' in url.lower()
        )
        
        return is_ec_europa and has_special_path

    def extract_grant_details(self, url: str, driver: Optional[webdriver.Chrome] = None) -> Dict[str, Any]:
        """
        Extract grant details from a single URL.
        
        Uses adaptive extraction strategy: for ec.europa.eu tender/topic detail pages,
        applies aggressive extraction with longer waits and additional scrolling to ensure
        all JavaScript-rendered content is loaded before GPT extraction.
        
        Args:
            url: URL to extract from
            driver: Optional Selenium driver (creates new one if None)
            
        Returns:
            Dictionary with grant details and metadata
        """
        own_driver = driver is None
        
        if own_driver:
            driver = self._create_driver(url)
        
        clicked_elements = 0
        is_special_ec_url = self._is_ec_europa_special_url(url)
        
        try:
            logger.info(f"Extracting grant details from: {url}")
            
            # Determine if this requires aggressive extraction strategy
            if is_special_ec_url:
                logger.info(f"✓ Using aggressive extraction strategy for EC Europa special URL")
            
            # Load page with Selenium
            start_time = time.time()
            driver.get(url)
            
            # Adaptive initial wait time based on URL type
            # EC Europa special URLs need longer initial wait to load JavaScript content
            if is_special_ec_url:
                logger.debug("Waiting 4s (aggressive strategy) for page initialization")
                time.sleep(4)  # Increased from 2s to 4s for ec.europa.eu tender/topic pages
            else:
                time.sleep(2)  # Standard wait for other pages
            
            # Click expandable elements (tabs, "show more", accordions, etc.)
            # This reveals hidden content before extraction
            if is_special_ec_url:
                # For EC Europa pages, use aggressive click strategy with longer delays
                logger.debug("Using aggressive click delays (0.5s) for expandable elements")
                clicked_elements = click_tabs_and_expandable_elements(driver)
                # Note: click_delay is controlled via config, but we need to apply additional scrolling
                
                # After clicking expandable elements, perform aggressive scrolling
                # This ensures all lazy-loaded content is rendered
                logger.debug("Performing aggressive scrolling (5 iterations) for ec.europa.eu page")
                scroll_start = time.time()
                last_height = driver.execute_script("return document.body.scrollHeight")
                
                for i in range(5):
                    # Scroll to bottom
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)  # Use 0.5s scroll delay for aggressive extraction
                    
                    # Check if height changed
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        logger.debug(f"  Height stabilized after {i + 1} aggressive scrolls")
                        break
                    last_height = new_height
                
                scroll_elapsed = time.time() - scroll_start
                logger.debug(f"Aggressive scrolling completed in {scroll_elapsed:.1f}s")
            else:
                # Standard extraction for other pages
                clicked_elements = click_tabs_and_expandable_elements(driver)
            
            # Get HTML content after expansion
            html_content = driver.page_source
            
            # For EC Europa pages, add an extra sleep before extraction to ensure all
            # JavaScript-rendered content is fully loaded
            if is_special_ec_url:
                logger.debug("Adding 1s extra wait before GPT extraction (aggressive strategy)")
                time.sleep(1)
            
            load_time = time.time() - start_time
            logger.debug(f"Page loaded in {load_time:.2f}s, HTML length: {len(html_content)}")
            
            # Apply preprocessing for EC Europa pages to reduce noise and improve accuracy
            original_html_size = len(html_content)
            if is_special_ec_url:
                preprocessed = preprocess_ec_europa_html(html_content, url)
                if preprocessed:
                    html_content = preprocessed
                    reduction_pct = (1 - len(html_content)/original_html_size) * 100
                    logger.info(f"✓ Preprocessing: {len(html_content)} chars ({reduction_pct:.1f}% reduction)")
                else:
                    logger.debug(f"⚠ Preprocessing returned None, using full HTML ({original_html_size} chars)")
            
            # Extract with GPT
            extraction_start = time.time()
            extracted_data = self._extract_with_gpt(html_content, url)
            extraction_time = time.time() - extraction_start
            
            logger.info(f"Extraction successful for {url} (took {extraction_time:.2f}s)")
            
            # Check if page is actually a grant - with robust error handling
            try:
                is_grant_value = extracted_data.get('is_grant')
            except AttributeError:
                logger.error(f"extracted_data is not a dict: {type(extracted_data)}, value: {extracted_data}")
                raise
            
            if is_grant_value is False:
                # Special handling for EC Europa pages: ignore is_grant=false and use extracted data anyway
                if is_special_ec_url:
                    logger.info(f"⚠ GPT returned is_grant=false for EC Europa URL, but using data anyway (aggressive strategy override)")
                    result = {
                        'url': url,
                        'title': extracted_data.get('title'),
                        'organization': extracted_data.get('organization'),
                        'abstract': extracted_data.get('abstract'),
                        'deadline': extracted_data.get('deadline'),
                        'funding_amount': extracted_data.get('funding_amount'),
                        'extraction_date': datetime.now().isoformat(),
                        'extraction_success': True,  # Treat as success for EC URLs despite is_grant=false
                        'error': None,
                        'is_grant': True,  # Override GPT's is_grant result
                        'note': 'Data extracted using aggressive strategy for EC Europa URL despite GPT is_grant=false'
                    }
                else:
                    # Standard handling for non-EC URLs
                    result = {
                        'url': url,
                        'title': None,
                        'organization': None,
                        'abstract': None,
                        'deadline': None,
                        'funding_amount': None,
                        'extraction_date': datetime.now().isoformat(),
                        'extraction_success': False,
                        'error': f"Not a grant page: {extracted_data.get('invalid_reason', 'Unknown')}",
                        'is_grant': False
                    }
            else:
                # Add metadata for successful grant extraction
                result = {
                    'url': url,
                    'title': extracted_data.get('title'),
                    'organization': extracted_data.get('organization'),
                    'abstract': extracted_data.get('abstract'),
                    'deadline': extracted_data.get('deadline'),
                    'funding_amount': extracted_data.get('funding_amount'),
                    'extraction_date': datetime.now().isoformat(),
                    'extraction_success': True,
                    'error': None,
                    'is_grant': True
                }
                
                # Fallback: If GPT didn't extract deadline, try regex pattern matching
                if result['deadline'] is None:
                    fallback_deadline = extract_deadline_with_regex(html_content)
                    if fallback_deadline:
                        result['deadline'] = fallback_deadline
                        logger.info(f"✓ Deadline recovered via regex fallback: {fallback_deadline}")
            
            # Update site profile with results
            deadline_found = result.get('deadline') is not None
            funding_found = result.get('funding_amount') is not None
            self.site_profiles.update_site_profile(
                url,
                deadline_found=deadline_found,
                funding_found=funding_found,
                expandable_elements_clicked=clicked_elements
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract from {url}: {type(e).__name__}: {e}")
            
            # Update profile even on failure
            self.site_profiles.update_site_profile(
                url,
                deadline_found=False,
                funding_found=False,
                expandable_elements_clicked=clicked_elements,
                notes=f"Extraction failed: {type(e).__name__}"
            )
            
            return {
                'url': url,
                'title': None,
                'organization': None,
                'abstract': None,
                'deadline': None,
                'funding_amount': None,
                'extraction_date': datetime.now().isoformat(),
                'extraction_success': False,
                'error': str(e)
            }
        
        finally:
            if own_driver:
                driver.quit()
    
    def _save_grants_incrementally(
        self,
        output_file: Path,
        grants: List[Dict[str, Any]],
        classifications: Optional[Dict[str, Dict[str, Any]]] = None,
        keywords: Optional[Dict[str, Any]] = None,
        keyword_classifier: Optional[Any] = None
    ) -> None:
        """
        Save extracted grants incrementally to the output file.
        
        This maintains the complete structure with grants, notifications, stats, and model info,
        similar to the final output format.
        
        Args:
            output_file: Path where to save the grants
            grants: List of extracted grant dictionaries
            classifications: Optional dict mapping URLs to classification data
            keywords: Optional keywords dict for matching
            keyword_classifier: Optional classifier instance for keyword matching
        """
        # Build complete grant entries with classification and keyword matching data
        complete_grants = []
        
        for grant in grants:
            url = grant['url']
            classification = classifications.get(url, {}) if classifications else {}
            
            # Match keywords if classifier and keywords are provided
            matched_keywords = []
            recipients = []
            
            if keywords and keyword_classifier and grant.get('extraction_success'):
                matched_keywords, recipients = keyword_classifier._match_keywords_to_content(
                    grant,
                    keywords
                )
            
            # Build complete grant entry
            grant_entry = {
                'url': url,
                'title': grant.get('title'),
                'organization': grant.get('organization'),
                'deadline': grant.get('deadline'),
                'funding_amount': grant.get('funding_amount'),
                'abstract': grant.get('abstract'),
                'category': classification.get('category', 'single_grant'),
                'classification_reason': classification.get('reason', ''),
                'extraction_success': grant.get('extraction_success', False),
                'extraction_date': grant.get('extraction_date'),
                'extraction_error': grant.get('error'),
                'matched_keywords': matched_keywords,
                'recipients': recipients
            }
            complete_grants.append(grant_entry)
        
        # Build notifications mapping
        notifications = {}
        for grant in complete_grants:
            if not grant.get('recipients'):
                continue
            
            for email in grant['recipients']:
                if email not in notifications:
                    notifications[email] = {
                        'matched_grants': [],
                        'total_grants': 0
                    }
                
                notifications[email]['matched_grants'].append({
                    'url': grant['url'],
                    'title': grant['title'],
                    'deadline': grant['deadline'],
                    'funding_amount': grant['funding_amount'],
                    'matched_keywords': grant['matched_keywords']
                })
                notifications[email]['total_grants'] += 1
        
        # Calculate statistics
        extraction_success = sum(1 for g in complete_grants if g.get('extraction_success', False))
        stats = {
            'total_extracted': len(complete_grants),
            'extraction_success': extraction_success,
            'total_recipients': len(notifications),
            'total_matched_grants': sum(n['total_grants'] for n in notifications.values())
        }
        
        # Build and save output
        output_data = {
            'grants': complete_grants,
            'notifications': notifications,
            'stats': stats,
            'model': self.model
        }
        
        from utils.file_utils import save_json
        save_json(output_data, output_file)
        
        logger.debug(f"Incrementally saved {len(complete_grants)} grants to {output_file}")
    
    def extract_batch_parallel(
        self,
        urls: List[str],
        cache_manager: Optional[Any] = None,
        force_refresh: bool = False,
        output_file: Optional[Path] = None,
        classifications: Optional[Dict[str, Dict[str, Any]]] = None,
        keywords: Optional[Dict[str, Any]] = None,
        keyword_classifier: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract grant details from multiple URLs in parallel.
        
        Args:
            urls: List of URLs to extract from
            cache_manager: Optional cache manager for caching results
            force_refresh: If True, ignore cache and re-extract
            output_file: Optional path to save grants incrementally
            classifications: Optional dict mapping URLs to classification data
            keywords: Optional keywords dict for matching
            keyword_classifier: Optional classifier instance for keyword matching
            
        Returns:
            List of grant detail dictionaries
        """
        if not urls:
            logger.warning("No URLs to extract")
            return []
        
        logger.info(f"Starting parallel extraction of {len(urls)} grants with {self.parallel_workers} workers")
        
        results = []
        urls_to_extract = []
        
        # Check cache first
        if cache_manager and not force_refresh:
            for url in urls:
                cached = cache_manager.get_cached_grant(url)
                if cached:
                    logger.debug(f"Using cached data for: {url}")
                    results.append(cached)
                else:
                    urls_to_extract.append(url)
            
            logger.info(f"Found {len(results)} cached, extracting {len(urls_to_extract)} new grants")
        else:
            urls_to_extract = urls
        
        # Extract in parallel
        if urls_to_extract:
            with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
                # Submit all tasks
                future_to_url = {
                    executor.submit(self.extract_grant_details, url): url
                    for url in urls_to_extract
                }
                
                # Process completed tasks
                completed = 0
                for future in as_completed(future_to_url):
                    completed += 1
                    url = future_to_url[future]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        
                        # Update cache
                        if cache_manager and result['extraction_success']:
                            cache_manager.update_cache(url, result)
                        
                        # Save incrementally if output_file is provided
                        if output_file:
                            self._save_grants_incrementally(
                                output_file=output_file,
                                grants=results,
                                classifications=classifications,
                                keywords=keywords,
                                keyword_classifier=keyword_classifier
                            )
                        
                        if completed % 10 == 0:
                            logger.info(f"Progress: {completed}/{len(urls_to_extract)} extractions completed")
                    
                    except Exception as e:
                        logger.error(f"Extraction failed for {url}: {e}")
                        results.append({
                            'url': url,
                            'title': None,
                            'organization': None,
                            'abstract': None,
                            'deadline': None,
                            'funding_amount': None,
                            'extraction_date': datetime.now().isoformat(),
                            'extraction_success': False,
                            'error': str(e)
                        })
        
        logger.info(f"Parallel extraction complete: {len(results)} grants processed")
        
        # Calculate success rate
        successful = sum(1 for r in results if r.get('extraction_success', False))
        logger.info(f"Success rate: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
        
        return results


def extract_grants(
    urls: List[str],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    cache_manager: Optional[Any] = None,
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    Convenience function to extract grant details from URLs.
    
    Args:
        urls: List of URLs to extract from
        api_key: OpenAI API key (uses config if None)
        model: Model name (uses config if None)
        cache_manager: Optional cache manager
        force_refresh: If True, ignore cache
        
    Returns:
        List of grant detail dictionaries
    """
    extractor = GrantExtractor(api_key=api_key, model=model)
    return extractor.extract_batch_parallel(urls, cache_manager, force_refresh)
