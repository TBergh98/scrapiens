"""OpenAI-based link classification module."""

import time
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
import threading
from datetime import datetime
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
    
    def _classify_with_regex(self, links: List[str]) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Classify links using regex patterns.
        
        Returns:
            Tuple of (classified_results, unclassified_links)
            - classified_results: List of successfully regex-classified results
            - unclassified_links: List of links that didn't match any pattern (to send to LLM)
        """
        # Define regex patterns for each category
        # Note: order matters! Single grant patterns are checked first
        single_grant_patterns = [
            # Singular forms and specific details pages
            r'\b(bando|grant|funding|detail|submission|application|fellowship)\b',
            r'/details?(/|$|[?#])',
            r'/grant(/[^/]|$|[?#])',  # /grant/ or /grant with ID
            r'/call(/[^/]|$|[?#])',  # /call/ (singular with ID, NOT /calls/)
            r'/bando(/[^/]|$|[?#])',  # /bando/ (Italian singular with ID)
            r'(/|[?#])(detail|award|opportunity)(/|[?#]|$)',  # specific pages
        ]
        
        grant_list_patterns = [
            # Plural forms indicating lists/collections
            r'\b(bandi|grants|fundings|calls|opportunities|list\s+of|search|browse|directory)\b',
            r'/bandi(/|$|[?#])',  # plural
            r'/grants?s(/|$|[?#])',  # /grants or /grantss
            r'/fundings?s(/|$|[?#])',  # /fundings plural
            r'/calls(/|$|[?#])',  # /calls (plural, without ID)
            r'/opportunities(/|$|[?#])',  # plural
            r'/search(/|$|[?#])',
            r'/browse(/|$|[?#])',
            r'/directory(/|$|[?#])',
            r'(list|directory|index)\..*$',
            r'/opportunities(/|$|[?#])',
        ]
        
        other_patterns = [
            r'\b(about|chi\s+siamo|contatti?|contact|news|blog|faq|help|support|privacy|terms|policy)\b',
            r'/about(/|$|[?#])',
            r'/contact(/|$|[?#])',
            r'/news(/|$|[?#])',
            r'/blog(/|$|[?#])',
            r'/help(/|$|[?#])',
            r'linkedin',
        ]
        
        classified_results = []
        unclassified_links = []
        
        for url in links:
            url_lower = url.lower()
            classified = False
            
            # Check single_grant patterns
            for pattern in single_grant_patterns:
                if re.search(pattern, url_lower, re.IGNORECASE):
                    classified_results.append({
                        'url': url,
                        'category': 'single_grant',
                        'reason': 'Matched regex pattern for single grant'
                    })
                    classified = True
                    break
            
            if classified:
                continue
            
            # Check grant_list patterns
            for pattern in grant_list_patterns:
                if re.search(pattern, url_lower, re.IGNORECASE):
                    classified_results.append({
                        'url': url,
                        'category': 'grant_list',
                        'reason': 'Matched regex pattern for grant list'
                    })
                    classified = True
                    break
            
            if classified:
                continue
            
            # Check other patterns
            for pattern in other_patterns:
                if re.search(pattern, url_lower, re.IGNORECASE):
                    classified_results.append({
                        'url': url,
                        'category': 'other',
                        'reason': 'Matched regex pattern for other page'
                    })
                    classified = True
                    break
            
            if not classified:
                unclassified_links.append(url)
        
        return classified_results, unclassified_links

    def classify_links(
        self,
        links: List[str],
        batch_size: int = 50,
        show_progress: bool = True,
        output_file: Optional[Path] = None,
        incremental_save: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Classify a list of links into categories using regex-first approach.
        
        Process:
        1. First, classify with regex patterns (fast, local)
        2. Then, send unclassified links to LLM (accurate, but slower/more expensive)
        
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
            - reason: Explanation of classification
        """
        logger.info(f"Classifying {len(links)} links")
        
        # Step 1: Regex classification
        logger.info("Step 1: Regex-based pre-filtering")
        regex_results, unclassified_links = self._classify_with_regex(links)
        logger.info(f"  - Regex classified: {len(regex_results)} links")
        logger.info(f"  - Remaining for LLM: {len(unclassified_links)} links")
        
        all_results = regex_results.copy()

        # Save after regex phase if incremental saving is enabled
        if incremental_save and output_file is not None:
            stats_partial = {
                'total_links': len(all_results),
                'single_grant': sum(1 for c in all_results if c.get('category') == 'single_grant'),
                'grant_list': sum(1 for c in all_results if c.get('category') == 'grant_list'),
                'other': sum(1 for c in all_results if c.get('category') == 'other'),
                'error': sum(1 for c in all_results if c.get('category') == 'error'),
            }
            self._save_classification_incrementally(output_file, all_results, {'stats': stats_partial})
        
        # Step 2: LLM classification for unclassified links
        if unclassified_links:
            logger.info("Step 2: LLM-based classification for unmatched URLs")
            
            # Process in batches
            for i in range(0, len(unclassified_links), batch_size):
                batch = unclassified_links[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(unclassified_links) + batch_size - 1) // batch_size
                
                logger.info(f"  - Processing LLM batch {batch_num}/{total_batches} ({len(batch)} links)")
                
                try:
                    batch_results = self._classify_batch(batch, show_progress)
                    all_results.extend(batch_results)

                    # Save after each batch if incremental saving is enabled
                    if incremental_save and output_file is not None:
                        stats_partial = {
                            'total_links': len(all_results),
                            'single_grant': sum(1 for c in all_results if c.get('category') == 'single_grant'),
                            'grant_list': sum(1 for c in all_results if c.get('category') == 'grant_list'),
                            'other': sum(1 for c in all_results if c.get('category') == 'other'),
                            'error': sum(1 for c in all_results if c.get('category') == 'error'),
                        }
                        self._save_classification_incrementally(output_file, all_results, {'stats': stats_partial})
                    
                except Exception as e:
                    logger.error(f"Error processing batch {batch_num}: {e}", exc_info=True)
                    
                    # Add failed results
                    for url in batch:
                        all_results.append({
                            'url': url,
                            'category': 'error',
                            'reason': f'Classification failed: {str(e)}'
                        })

                    # Save current state including errors if incremental saving is enabled
                    if incremental_save and output_file is not None:
                        stats_partial = {
                            'total_links': len(all_results),
                            'single_grant': sum(1 for c in all_results if c.get('category') == 'single_grant'),
                            'grant_list': sum(1 for c in all_results if c.get('category') == 'grant_list'),
                            'other': sum(1 for c in all_results if c.get('category') == 'other'),
                            'error': sum(1 for c in all_results if c.get('category') == 'error'),
                        }
                        self._save_classification_incrementally(output_file, all_results, {'stats': stats_partial})
        else:
            logger.info("Step 2: All links classified by regex, skipping LLM")
        
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
    
    def _check_existing_classification(self, output_file: Path, total_links: int) -> tuple[bool, bool, Dict[str, Any]]:
        """
        Check if classification output file exists and if it's complete or partial.
        
        Args:
            output_file: Path to classification output file
            total_links: Total number of links to classify
            
        Returns:
            Tuple of (should_continue, is_complete, existing_data)
            - should_continue: Whether to continue with existing data or skip
            - is_complete: Whether all links are already classified
            - existing_data: The existing classification data if file exists
        """
        if not output_file.exists():
            return True, False, {}
        
        try:
            existing_data = load_json(output_file)
            existing_classifications = existing_data.get('classifications', [])
            
            if not existing_classifications:
                logger.info("Output file exists but contains no classifications")
                return True, False, existing_data
            
            classified_count = len(existing_classifications)
            
            if classified_count == total_links:
                logger.info(f"✓ All {classified_count} links are already classified")
                
                # Ask user if they want to use existing results
                while True:
                    response = input("Use existing classification results? [y/n/force-reclassify]: ").strip().lower()
                    if response == 'y':
                        return False, True, existing_data  # Use existing, don't continue
                    elif response == 'n':
                        return True, False, {}  # Start fresh
                    elif response == 'force-reclassify':
                        return True, False, {}  # Start fresh
                    else:
                        print("Please enter 'y', 'n', or 'force-reclassify'")
            
            elif classified_count < total_links:
                remaining = total_links - classified_count
                logger.info(f"Partial classification found: {classified_count}/{total_links} links classified ({remaining} remaining)")
                
                # Ask user what to do
                while True:
                    response = input(f"Continue with existing results ({classified_count} done)? [y/n/reclassify-all]: ").strip().lower()
                    if response == 'y':
                        return True, False, existing_data  # Continue from where we left off
                    elif response == 'n' or response == 'skip':
                        return False, True, existing_data  # Skip, use partial
                    elif response == 'reclassify-all':
                        return True, False, {}  # Start fresh
                    else:
                        print("Please enter 'y', 'n', or 'reclassify-all'")
            
            return True, False, existing_data
            
        except Exception as e:
            logger.warning(f"Could not read existing output file: {e}")
            return True, False, {}
    
    def _save_classification_incrementally(self, output_file: Path, classifications: List[Dict], metadata: Dict[str, Any]):
        """
        Save classifications to JSON file incrementally.
        
        Args:
            output_file: Path to save classification file
            classifications: List of classification results
            metadata: Additional metadata (model, stats, etc.)
        """
        output_data = {
            'classifications': classifications,
            'model': self.model,
            'timestamp': datetime.now().isoformat(),
            **metadata
        }
        
        save_json(output_data, output_file)
        logger.debug(f"Saved {len(classifications)} classifications to {output_file}")
    
    def classify_from_file(
        self,
        input_file: Path,
        output_file: Path,
        keywords_dict: Optional[Dict[str, List[str]]] = None,
        batch_size: int = 50,
        extract_details: bool = False,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Load links from a JSON file and classify them incrementally.
        Saves classification results to output_file WITHOUT extraction.
        
        Args:
            input_file: Path to input JSON file (from deduplicator) - link_unificati.json
            output_file: Path to save classification results - classified_links.json
            keywords_dict: Optional mapping of email to keywords (not used in classification-only mode)
            batch_size: Number of links per batch
            extract_details: Ignored in classify-only mode (always False)
            force_refresh: If True, ignore existing results and reclassify
            
        Returns:
            Classification results with statistics
        """
        logger.info(f"Loading links from {input_file}")
        
        data = load_json(input_file)
        
        if not data:
            raise ValueError(f"Invalid or empty input file: {input_file}")
        
        # Handle new format with simple links list
        links = data.get('links', [])
        
        # Fallback to legacy formats for backward compatibility
        if not links:
            links_dict = data.get('links_with_keywords', {})
            if links_dict:
                links = list(links_dict.keys())
            else:
                unique_links = data.get('unique_links', [])
                links = unique_links if unique_links else []
        
        if not links:
            logger.warning("No links found in input file")
            return {
                'classifications': [],
                'stats': {
                    'total_links': 0,
                    'single_grant': 0,
                    'grant_list': 0,
                    'other': 0,
                    'error': 0,
                },
                'model': self.model
            }
        
        # Check if output file exists and ask user what to do
        if not force_refresh:
            should_continue, is_complete, existing_data = self._check_existing_classification(
                output_file, len(links)
            )
            
            if is_complete:
                # User wants to use existing results
                logger.info("Using existing classification results")
                
                # Calculate stats from existing data
                existing_classifications = existing_data.get('classifications', [])
                stats = {
                    'total_links': len(existing_classifications),
                    'single_grant': sum(1 for c in existing_classifications if c['category'] == 'single_grant'),
                    'grant_list': sum(1 for c in existing_classifications if c['category'] == 'grant_list'),
                    'other': sum(1 for c in existing_classifications if c['category'] == 'other'),
                    'error': sum(1 for c in existing_classifications if c['category'] == 'error'),
                }
                
                return {
                    'classifications': existing_classifications,
                    'stats': stats,
                    'model': self.model
                }
            
            if not should_continue:
                # User wants to skip/skip reclassifying
                logger.info("Skipping classification")
                return {
                    'classifications': existing_data.get('classifications', []),
                    'stats': existing_data.get('stats', {}),
                    'model': self.model
                }
        
        # Classify all links
        logger.info(f"Classifying {len(links)} URLs (batch_size={batch_size})")
        classifications = self.classify_links(
            links,
            batch_size=batch_size,
            show_progress=True,
            output_file=output_file,
            incremental_save=True
        )
        
        # Calculate statistics
        stats = {
            'total_links': len(classifications),
            'single_grant': sum(1 for c in classifications if c['category'] == 'single_grant'),
            'grant_list': sum(1 for c in classifications if c['category'] == 'grant_list'),
            'other': sum(1 for c in classifications if c['category'] == 'other'),
            'error': sum(1 for c in classifications if c['category'] == 'error'),
        }
        
        # Save incrementally
        self._save_classification_incrementally(
            output_file,
            classifications,
            {'stats': stats}
        )
        
        logger.info(f"Classification results saved to {output_file}")
        logger.info(f"Statistics: {stats}")
        
        results = {
            'classifications': classifications,
            'stats': stats,
            'model': self.model
        }
        
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
