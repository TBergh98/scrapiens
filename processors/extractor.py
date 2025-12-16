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
        
        prompt_template = config.get('extractor.extraction_prompt', '''
Analyze the following HTML content from a research grant/call page and extract the following information:

1. **title**: The title of the grant/call (string)
2. **organization**: The organization offering the grant (string)
3. **abstract**: A brief summary or description of the grant (string, max 500 characters)
4. **deadline**: The application deadline (CRITICAL: ONLY if EXPLICITLY stated in the text. Return null if not found or ambiguous. Format as YYYY-MM-DD. DO NOT invent or guess dates.)
5. **funding_amount**: The funding amount available (string, e.g., "€500,000" or "up to $1M")

IMPORTANT RULES:
- Return ONLY factual information that is explicitly present in the HTML
- For deadline: Search in multiple places:
  * Visible text (scadenza, deadline, data limite, application deadline, closing date)
  * JSON-LD structured data: Look for "deadline", "endDate", "expires", "applicationDeadline" fields
  * HTML5 data attributes: Check data-deadline, data-date, data-end, data-expiration attributes
  * HTML comments containing dates: <!-- deadline: ... --> or similar
  * Script tags with JSON: <script type="application/ld+json"> or similar
  * Meta tags: Check og:expiration, article:published_time, article:expiration_time
  * If you see text like "scadenza: 31/12/2024" or "deadline: December 31, 2024", extract it
  * If dates are vague like "coming soon" or "TBD", return null
- For funding_amount: Look for keywords like "importo", "finanziamento", "budget", "funding", "amount" in visible text and data attributes
- If any field cannot be found explicitly, return null (not empty string)
- Return valid JSON only

URL: {url}

HTML Content (truncated to first 15000 chars):
{html}

Return a JSON object with these exact keys: title, organization, abstract, deadline, funding_amount
''')
        
        # Truncate HTML to avoid token limits
        html_truncated = html_content[:15000]
        
        prompt = prompt_template.format(url=url, html=html_truncated)
        
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
        
        try:
            result = json.loads(response_text)
            
            # Fix malformed JSON with escaped quotes in keys (e.g., "\"is_grant\"" instead of "is_grant")
            # This can happen when GPT returns doubly-encoded JSON
            if isinstance(result, dict):
                fixed_result = {}
                for key, value in result.items():
                    # Remove quotes from key if present
                    clean_key = key.strip('"\'')
                    fixed_result[clean_key] = value
                result = fixed_result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from GPT response: {e}")
            logger.debug(f"Raw response: {response_text}")
            raise ValueError(f"Invalid JSON from GPT: {str(e)}")
        
        # Handle non-grant pages (is_grant: false)
        try:
            is_grant = result.get('is_grant', True)
        except (AttributeError, TypeError) as e:
            logger.error(f"Error accessing 'is_grant' field in result: {e}. Result type: {type(result)}")
            raise ValueError(f"Invalid result structure: {str(e)}")
        
        if not is_grant:
            logger.info(f"Page is not a grant: {result.get('invalid_reason', 'No reason provided')}")
            return {
                'is_grant': False,
                'invalid_reason': result.get('invalid_reason'),
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
    
    def extract_grant_details(self, url: str, driver: Optional[webdriver.Chrome] = None) -> Dict[str, Any]:
        """
        Extract grant details from a single URL.
        
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
        
        try:
            logger.info(f"Extracting grant details from: {url}")
            
            # Load page with Selenium
            start_time = time.time()
            driver.get(url)
            
            # Wait for page to load
            time.sleep(2)
            
            # Click expandable elements (tabs, "show more", accordions, etc.)
            # This reveals hidden content before extraction
            clicked_elements = click_tabs_and_expandable_elements(driver)
            
            # Get HTML content after expansion
            html_content = driver.page_source
            
            load_time = time.time() - start_time
            logger.debug(f"Page loaded in {load_time:.2f}s, HTML length: {len(html_content)}")
            
            # Extract with GPT
            extraction_start = time.time()
            extracted_data = self._extract_with_gpt(html_content, url)
            extraction_time = time.time() - extraction_start
            
            logger.info(f"Extraction successful for {url} (took {extraction_time:.2f}s)")
            
            # Check if page is actually a grant
            if extracted_data.get('is_grant') is False:
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
    
    def extract_batch_parallel(
        self,
        urls: List[str],
        cache_manager: Optional[Any] = None,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Extract grant details from multiple URLs in parallel.
        
        Args:
            urls: List of URLs to extract from
            cache_manager: Optional cache manager for caching results
            force_refresh: If True, ignore cache and re-extract
            
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
