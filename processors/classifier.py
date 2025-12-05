"""OpenAI-based link classification module."""

import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
import threading
from openai import OpenAI
from utils.logger import get_logger
from utils.file_utils import save_json, load_json
from utils.cache import CacheManager
from config.settings import get_config

logger = get_logger(__name__)


class LinkClassifier:
    """Classifier for research grant links using OpenAI API."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the classifier.
        
        Args:
            api_key: OpenAI API key (uses config if None)
            model: Model name (uses config if None)
        """
        config = get_config()
        
        self.api_key = api_key or config.openai_api_key
        self.model = model or config.get('openai.model', 'gpt-4o-mini')
        self.timeout = config.get('openai.timeout', 300)
        self.progress_interval = config.get('openai.progress_interval', 10)
        
        self.client = OpenAI(api_key=self.api_key)
        
        logger.info(f"Initialized LinkClassifier with model: {self.model}")
    
    def _progress_indicator(self, stop_event: threading.Event):
        """Print progress messages while waiting for API response."""
        counter = 1
        while not stop_event.is_set():
            time.sleep(self.progress_interval)
            if not stop_event.is_set():
                logger.info(f"Still processing... ({counter * self.progress_interval} seconds elapsed)")
                counter += 1
    
    def classify_links(
        self,
        links: List[str],
        batch_size: int = 50,
        show_progress: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Classify a list of links into categories.
        
        Categories:
        - single_grant: URL leads to a single research grant/call page
        - grant_list: URL leads to a list of multiple grants
        - other: Generic pages (contacts, about, home, etc.)
        
        Args:
            links: List of URL strings to classify
            batch_size: Number of links to classify per API call
            show_progress: Whether to show progress indicator
            
        Returns:
            List of classification results, each with:
            - url: Original URL
            - category: Classification category
            - confidence: Confidence score (0-1)
            - reason: Explanation of classification
        """
        logger.info(f"Classifying {len(links)} links in batches of {batch_size}")
        
        all_results = []
        
        # Process in batches
        for i in range(0, len(links), batch_size):
            batch = links[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(links) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} links)")
            
            try:
                batch_results = self._classify_batch(batch, show_progress)
                all_results.extend(batch_results)
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {e}", exc_info=True)
                
                # Add failed results
                for url in batch:
                    all_results.append({
                        'url': url,
                        'category': 'error',
                        'confidence': 0.0,
                        'reason': f'Classification failed: {str(e)}'
                    })
        
        logger.info(f"Classification complete: {len(all_results)} links processed")
        
        return all_results
    
    def _classify_batch(self, links: List[str], show_progress: bool) -> List[Dict[str, Any]]:
        """Classify a single batch of links."""
        config = get_config()
        
        # Build prompt
        prompt_template = config.get('openai.classification_prompt')
        urls_text = '\n'.join(f"{i+1}. {url}" for i, url in enumerate(links))
        prompt = prompt_template.format(urls=urls_text)
        
        # Start progress indicator
        stop_progress = threading.Event()
        progress_thread = None
        
        if show_progress:
            progress_thread = threading.Thread(
                target=self._progress_indicator,
                args=(stop_progress,),
                daemon=True
            )
            progress_thread.start()
        
        try:
            logger.debug("Sending API request...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing URLs to determine if they lead to research grant/call pages. You respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                timeout=self.timeout
            )
            
            # Stop progress indicator
            if show_progress:
                stop_progress.set()
                if progress_thread:
                    progress_thread.join(timeout=1)
            
            logger.debug("API request completed")
            
            # Parse response
            response_text = response.choices[0].message.content
            
            if response_text is None:
                raise ValueError("API response content is None")
            
            # Try to extract JSON from response (might be wrapped in markdown code block)
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                response_text = response_text[json_start:json_end].strip()
            elif '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                response_text = response_text[json_start:json_end].strip()
            
            results = json.loads(response_text)
            
            # Validate results
            if not isinstance(results, list):
                raise ValueError("API response is not a list")
            
            # Ensure all results have required fields
            validated_results = []
            for result in results:
                validated_results.append({
                    'url': result.get('url', ''),
                    'category': result.get('category', 'unknown'),
                    'confidence': float(result.get('confidence', 0.5)),
                    'reason': result.get('reason', 'No reason provided')
                })
            
            return validated_results
            
        except Exception as e:
            # Stop progress indicator
            if show_progress:
                stop_progress.set()
                if progress_thread:
                    progress_thread.join(timeout=1)
            
            raise e
    
    def classify_from_file(
        self,
        input_file: Path,
        output_file: Path,
        keywords_dict: Optional[Dict[str, List[str]]] = None,
        batch_size: int = 50,
        extract_details: bool = True,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Load links from a JSON file, classify them, extract grant details, and save results.
        
        Args:
            input_file: Path to input JSON file (from deduplicator)
            output_file: Path to save classification results
            keywords_dict: Optional mapping of email to keywords for enriching results
            batch_size: Number of links per batch
            extract_details: Whether to extract grant details (default True)
            force_refresh: If True, ignore cache and re-extract
            
        Returns:
            Classification results with statistics
        """
        logger.info(f"Loading links from {input_file}")
        
        data = load_json(input_file)
        
        if not data:
            raise ValueError(f"Invalid or empty input file: {input_file}")
        
        # Handle new format with links_with_keywords or legacy format
        links_dict = data.get('links_with_keywords', {})
        if not links_dict:
            # Legacy format support: just unique_links list
            unique_links = data.get('unique_links', [])
            links_dict = {link: [] for link in unique_links}
        
        links = list(links_dict.keys())
        
        if not links:
            logger.warning("No links found in input file")
            return {
                'grants': [],
                'notifications': {},
                'stats': {
                    'total_links': 0,
                    'single_grant': 0,
                    'grant_list': 0,
                    'other': 0,
                    'error': 0,
                    'avg_confidence': 0,
                    'extracted': 0,
                    'extraction_success': 0
                },
                'model': self.model
            }
        
        # Classify
        logger.info("Step 1/3: Classifying URLs")
        classifications = self.classify_links(links, batch_size=batch_size)
        
        # Extract grant details for single_grant URLs
        grants = []
        
        if extract_details:
            logger.info("Step 2/3: Extracting grant details")
            
            # Filter only single_grant URLs
            single_grant_urls = [
                c['url'] for c in classifications 
                if c['category'] == 'single_grant'
            ]
            
            grant_list_count = sum(1 for c in classifications if c['category'] == 'grant_list')
            if grant_list_count > 0:
                logger.info(f"Ignoring {grant_list_count} URLs classified as 'grant_list' (multi-grant pages)")
            
            if single_grant_urls:
                logger.info(f"Extracting details from {len(single_grant_urls)} single grant URLs")
                
                # Import extractor here to avoid circular dependency
                from processors.extractor import GrantExtractor
                
                # Initialize cache
                cache_manager = CacheManager()
                
                # Extract with parallel processing
                extractor = GrantExtractor()
                extracted_grants = extractor.extract_batch_parallel(
                    single_grant_urls,
                    cache_manager=cache_manager,
                    force_refresh=force_refresh
                )
                
                # Merge classification and extraction data
                classification_map = {c['url']: c for c in classifications}
                
                for grant in extracted_grants:
                    url = grant['url']
                    classification = classification_map.get(url, {})
                    
                    # Match keywords to actual content
                    matched_keywords = []
                    recipients = []
                    
                    if keywords_dict and grant.get('extraction_success'):
                        matched_keywords, recipients = self._match_keywords_to_content(
                            grant,
                            keywords_dict
                        )
                    
                    # Build grant entry
                    grant_entry = {
                        'url': url,
                        'title': grant.get('title'),
                        'organization': grant.get('organization'),
                        'deadline': grant.get('deadline'),
                        'funding_amount': grant.get('funding_amount'),
                        'abstract': grant.get('abstract'),
                        'category': classification.get('category', 'single_grant'),
                        'classification_confidence': classification.get('confidence', 0),
                        'classification_reason': classification.get('reason', ''),
                        'extraction_success': grant.get('extraction_success', False),
                        'extraction_date': grant.get('extraction_date'),
                        'extraction_error': grant.get('error'),
                        'matched_keywords': matched_keywords,
                        'recipients': recipients
                    }
                    
                    grants.append(grant_entry)
            else:
                logger.warning("No single_grant URLs found to extract")
        else:
            logger.info("Skipping grant details extraction (extract_details=False)")
        
        # Build notifications mapping
        logger.info("Step 3/3: Building notifications")
        notifications = {}
        
        for grant in grants:
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
        stats = {
            'total_links': len(classifications),
            'single_grant': sum(1 for c in classifications if c['category'] == 'single_grant'),
            'grant_list': sum(1 for c in classifications if c['category'] == 'grant_list'),
            'other': sum(1 for c in classifications if c['category'] == 'other'),
            'error': sum(1 for c in classifications if c['category'] == 'error'),
            'avg_confidence': round(
                sum(c['confidence'] for c in classifications) / len(classifications),
                3
            ) if classifications else 0,
            'extracted': len(grants),
            'extraction_success': sum(1 for g in grants if g.get('extraction_success', False)),
            'total_recipients': len(notifications),
            'total_matched_grants': sum(n['total_grants'] for n in notifications.values())
        }
        
        results = {
            'grants': grants,
            'notifications': notifications,
            'stats': stats,
            'model': self.model
        }
        
        # Save results
        save_json(results, output_file)
        
        logger.info(f"Results saved to {output_file}")
        logger.info(f"Statistics: {stats}")
        logger.info(f"Total notifications: {len(notifications)} recipients, {stats['total_matched_grants']} matched grants")
        
        return results
    
    def _match_keywords_to_content(
        self,
        grant_details: Dict[str, Any],
        keywords_dict: Dict[str, List[str]]
    ) -> tuple[List[str], List[str]]:
        """
        Match keywords to actual grant content (title + abstract).
        
        Args:
            grant_details: Extracted grant details with title and abstract
            keywords_dict: Mapping of email to keywords
            
        Returns:
            Tuple of (matched_keywords, recipients)
        """
        # Get searchable content
        title = grant_details.get('title', '') or ''
        abstract = grant_details.get('abstract', '') or ''
        content = f"{title} {abstract}".lower()
        
        if not content.strip():
            logger.debug(f"No content to match for {grant_details.get('url')}")
            return [], []
        
        # Build reverse mapping: keyword -> list of emails
        keyword_to_recipients = {}
        for email, keywords in keywords_dict.items():
            for keyword in keywords:
                keyword_lower = str(keyword).strip().lower()
                if keyword_lower not in keyword_to_recipients:
                    keyword_to_recipients[keyword_lower] = []
                if email not in keyword_to_recipients[keyword_lower]:
                    keyword_to_recipients[keyword_lower].append(email)
        
        # Find matched keywords
        matched_keywords = set()
        recipients = set()
        
        for keyword_lower, emails in keyword_to_recipients.items():
            if keyword_lower in content:
                matched_keywords.add(keyword_lower)
                recipients.update(emails)
                logger.debug(f"Keyword match: '{keyword_lower}' in {grant_details.get('url')}")
        
        return sorted(list(matched_keywords)), sorted(list(recipients))


def classify_links(
    links: List[str],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    batch_size: int = 50
) -> List[Dict[str, Any]]:
    """
    Convenience function to classify links.
    
    Args:
        links: List of URL strings
        api_key: OpenAI API key (uses config if None)
        model: Model name (uses config if None)
        batch_size: Links per batch
        
    Returns:
        List of classification results
    """
    classifier = LinkClassifier(api_key=api_key, model=model)
    return classifier.classify_links(links, batch_size=batch_size)
