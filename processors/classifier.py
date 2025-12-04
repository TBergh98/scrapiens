"""OpenAI-based link classification module."""

import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
import threading
from openai import OpenAI
from utils.logger import get_logger
from utils.file_utils import save_json, load_json
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
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Load links from a JSON file, classify them, and save results.
        
        Args:
            input_file: Path to input JSON file (from deduplicator)
            output_file: Path to save classification results
            batch_size: Number of links per batch
            
        Returns:
            Classification results with statistics
        """
        logger.info(f"Loading links from {input_file}")
        
        data = load_json(input_file)
        
        if not data or 'unique_links' not in data:
            raise ValueError(f"Invalid input file format: {input_file}")
        
        links = data['unique_links']
        
        # Classify
        classifications = self.classify_links(links, batch_size=batch_size)
        
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
            ) if classifications else 0
        }
        
        results = {
            'classifications': classifications,
            'stats': stats,
            'model': self.model
        }
        
        # Save results
        save_json(results, output_file)
        
        logger.info(f"Classification results saved to {output_file}")
        logger.info(f"Statistics: {stats}")
        
        return results


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
