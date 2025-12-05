"""Grant details extraction module using GPT-4o and Selenium."""

import time
import json
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

logger = get_logger(__name__)


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
        
        logger.info(f"Initialized GrantExtractor with model: {self.model}")
    
    def _create_driver(self) -> webdriver.Chrome:
        """Create a Selenium WebDriver instance for extraction."""
        config = get_config()
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(5)
        driver.set_page_load_timeout(self.timeout)
        
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
- For deadline: If you see text like "scadenza: 31/12/2024" or "deadline: December 31, 2024", extract it. If dates are vague like "coming soon" or "TBD", return null
- For funding_amount: Look for keywords like "importo", "finanziamento", "budget", "funding", "amount"
- If any field cannot be found, return null (not empty string)
- Return valid JSON only

URL: {url}

HTML Content (truncated to first 8000 chars):
{html}

Return a JSON object with these exact keys: title, organization, abstract, deadline, funding_amount
''')
        
        # Truncate HTML to avoid token limits
        html_truncated = html_content[:8000]
        
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
        
        result = json.loads(response_text)
        
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
            driver = self._create_driver()
        
        try:
            logger.info(f"Extracting grant details from: {url}")
            
            # Load page with Selenium
            start_time = time.time()
            driver.get(url)
            
            # Wait for page to load
            time.sleep(2)
            
            # Get HTML content
            html_content = driver.page_source
            
            load_time = time.time() - start_time
            logger.debug(f"Page loaded in {load_time:.2f}s, HTML length: {len(html_content)}")
            
            # Extract with GPT
            extraction_start = time.time()
            extracted_data = self._extract_with_gpt(html_content, url)
            extraction_time = time.time() - extraction_start
            
            logger.info(f"Extraction successful for {url} (took {extraction_time:.2f}s)")
            
            # Add metadata
            result = {
                'url': url,
                'title': extracted_data.get('title'),
                'organization': extracted_data.get('organization'),
                'abstract': extracted_data.get('abstract'),
                'deadline': extracted_data.get('deadline'),
                'funding_amount': extracted_data.get('funding_amount'),
                'extraction_date': datetime.now().isoformat(),
                'extraction_success': True,
                'error': None
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract from {url}: {type(e).__name__}: {e}")
            
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
