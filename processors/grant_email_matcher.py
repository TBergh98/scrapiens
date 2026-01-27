"""
Grant-to-Email Keyword Matcher Module

This module reads extracted grant data and matches keywords against grant descriptions/titles,
then associates each grant with the emails whose keywords were found.

Architecture:
- Reads extracted_grants_*.json from intermediate_outputs/
- Reads keywords.yaml from input/
- Performs case-insensitive word-boundary keyword matching
- Outputs matched results with email associations
- Optionally filters out already-sent grants and expired deadlines

Performance optimizations:
- Inverted index: keyword -> list of emails
- Single-pass per grant: find all matching keywords at once, then map to emails
- Word boundary regex matching (\b) for precise matching
- Minimal memory footprint: stream processing concept
"""

import re
import json
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Set, Tuple, Optional
import yaml

from utils.file_utils import load_json, save_json
from utils.logger import get_logger
from utils.sent_grants_manager import SentGrantsManager
from config.settings import Config

logger = get_logger(__name__)


class GrantEmailMatcher:
    """Matcher for associating grants with emails based on keyword discovery in descriptions."""

    def __init__(self, config: Optional[Config] = None, sent_grants_manager: Optional[SentGrantsManager] = None):
        """
        Initialize the matcher.
        
        Args:
            config: Configuration object. If None, creates default Config.
            sent_grants_manager: Manager for tracking sent grants. If None, creates default manager.
        """
        self.config = config or Config()
        self.sent_grants_manager = sent_grants_manager or SentGrantsManager()
        self.keywords_data: Dict[str, List[str]] = {}
        self.keyword_to_emails: Dict[str, List[str]] = {}
        self.all_keywords_set: Set[str] = set()
        self.keyword_patterns: Dict[str, re.Pattern] = {}

    def load_keywords(self, keywords_file: str) -> bool:
        """
        Load keywords from YAML file.
        
        Args:
            keywords_file: Path to keywords.yaml
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(keywords_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data or 'keywords' not in data:
                logger.warning(f"No 'keywords' key found in {keywords_file}")
                self.keywords_data = {}
                return False
            
            self.keywords_data = data['keywords']
            logger.info(f"Loaded keywords for {len(self.keywords_data)} emails from {keywords_file}")
            
            # Pre-compile regex patterns for performance
            self._compile_patterns()
            return True
            
        except FileNotFoundError:
            logger.error(f"Keywords file not found: {keywords_file}")
            return False
        except Exception as e:
            logger.error(f"Error loading keywords: {e}")
            return False

    def _compile_patterns(self) -> None:
        """
        Build optimized keyword index with pre-compiled regex patterns.
        
        Maps each keyword (in lowercase) to the list of emails that have it.
        Pre-compiles regex patterns for each keyword to avoid compilation overhead.
        """
        # Normalize all keywords to lowercase and build reverse index
        self.keyword_to_emails: Dict[str, List[str]] = {}
        self.all_keywords_set: Set[str] = set()
        self.keyword_patterns: Dict[str, re.Pattern] = {}
        
        for email, keywords in self.keywords_data.items():
            for keyword in keywords:
                # Normalize keyword
                kw_lower = keyword.lower()
                if kw_lower not in self.keyword_to_emails:
                    self.keyword_to_emails[kw_lower] = []
                    # Pre-compile regex pattern with word boundaries
                    self.keyword_patterns[kw_lower] = re.compile(
                        rf'\b{re.escape(kw_lower)}\b',
                        re.IGNORECASE | re.UNICODE
                    )
                self.keyword_to_emails[kw_lower].append(email)
                self.all_keywords_set.add(kw_lower)

    def _extract_searchable_text(self, grant: Dict) -> Optional[str]:
        """
        Extract text to search from grant data.
        
        Priority: abstract > title
        Both are searched with OR logic if abstract is None.
        
        Args:
            grant: Grant data dictionary
            
        Returns:
            Combined searchable text or None if both abstract and title are None/empty
        """
        text_parts = []
        
        # Try abstract first
        abstract = grant.get('abstract', '').strip() if grant.get('abstract') else None
        if abstract:
            text_parts.append(abstract)
        
        # Try title as fallback/addition
        title = grant.get('title', '').strip() if grant.get('title') else None
        if title:
            text_parts.append(title)
        
        if not text_parts:
            return None
        
        # Combine all available text
        return ' '.join(text_parts)

    def _is_deadline_expired(self, deadline_str: Optional[str]) -> bool:
        """
        Check if a deadline has expired (passed today).
        
        Args:
            deadline_str: Deadline string in various date formats, or None
            
        Returns:
            True if deadline < today, False if deadline >= today or cannot parse
        """
        if not deadline_str:
            return False  # No deadline = not expired
        
        try:
            from dateutil import parser as date_parser
            deadline_date = date_parser.parse(deadline_str).date()
            return deadline_date < date.today()
        except Exception as e:
            logger.debug(f"Could not parse deadline '{deadline_str}': {e} - treating as not expired")
            return False

    def _filter_grants_for_recipient(
        self,
        grants: List[Dict],
        recipient_email: str,
        exclude_already_sent: bool = True,
        exclude_failed_extraction: bool = False,
        exclude_expired_deadline: bool = True
    ) -> Tuple[List[Dict], Dict]:
        """
        Filter grants for a specific recipient based on multiple criteria.
        
        Args:
            grants: List of grant dictionaries
            recipient_email: Email address to filter for
            exclude_already_sent: If True, exclude grants already sent+delivered to this recipient
            exclude_failed_extraction: If True, exclude grants with extraction_success=False.
                                       If False, allow retry of failed extractions.
            exclude_expired_deadline: If True, exclude grants with deadline < today
            
        Returns:
            Tuple of (filtered_grants, stats_dict)
        """
        stats = {
            'original_count': len(grants),
            'excluded_already_sent': 0,
            'excluded_failed_extraction': 0,
            'excluded_expired_deadline': 0,
            'final_count': 0
        }
        
        filtered = []
        
        for grant in grants:
            # Check if already sent to this recipient
            if exclude_already_sent:
                grant_url = grant.get('url')
                if grant_url and self.sent_grants_manager.was_sent_to(grant_url, recipient_email):
                    stats['excluded_already_sent'] += 1
                    continue
            
            # Check if extraction failed
            if exclude_failed_extraction:
                if not grant.get('extraction_success', True):
                    stats['excluded_failed_extraction'] += 1
                    continue
            
            # Check if deadline expired
            if exclude_expired_deadline:
                deadline_str = grant.get('deadline')
                if deadline_str and self._is_deadline_expired(deadline_str):
                    stats['excluded_expired_deadline'] += 1
                    continue
            
            # Grant passed all filters
            filtered.append(grant)
        
        stats['final_count'] = len(filtered)
        return filtered, stats

    def _extract_searchable_text(self, grant: Dict) -> Optional[str]:

        """
        Extract text to search from grant data.
        
        Priority: abstract > title
        Both are searched with OR logic if abstract is None.
        
        Args:
            grant: Grant data dictionary
            
        Returns:
            Combined searchable text or None if both abstract and title are None/empty
        """
        text_parts = []
        
        # Try abstract first
        abstract = grant.get('abstract', '').strip() if grant.get('abstract') else None
        if abstract:
            text_parts.append(abstract)
        
        # Try title as fallback/addition
        title = grant.get('title', '').strip() if grant.get('title') else None
        if title:
            text_parts.append(title)
        
        if not text_parts:
            return None
        
        # Combine all available text
        return ' '.join(text_parts)

    def match_grants_to_emails(
        self,
        grants: List[Dict],
        exclude_already_sent: bool = True,
        exclude_failed_extraction: bool = False,
        exclude_expired_deadline: bool = True
    ) -> Tuple[List[Dict], int, Dict]:
        """
        Match grants to emails based on keyword discovery.
        
        Optimized: for each grant, find ALL matching keywords once,
        then map those keywords to emails.
        
        Args:
            grants: List of grant dictionaries
            exclude_already_sent: If True, exclude grants already sent+delivered to recipients
            exclude_failed_extraction: If True, exclude grants with extraction_success=False
            exclude_expired_deadline: If True, exclude grants with deadline < today
            
        Returns:
            Tuple of (matched_results, count_of_grants_with_matches, filter_stats_dict)
        """
        results = []
        grants_with_matches = 0
        filter_stats = {
            'total_grants': len(grants),
            'excluded_already_sent': 0,
            'excluded_failed_extraction': 0,
            'excluded_expired_deadline': 0,
            'grants_with_matches': 0,
            'per_recipient_stats': {}
        }
        
        logger.info(f"Starting keyword matching for {len(grants)} grants...")
        
        # Track stats per email during filtering
        per_recipient_excluded = {email: {'already_sent': 0, 'failed': 0, 'expired': 0} for email in self.keywords_data.keys()}
        
        for grant_idx, grant in enumerate(grants):
            # Extract searchable text
            searchable_text = self._extract_searchable_text(grant)
            
            if not searchable_text:
                logger.debug(f"Grant {grant_idx}: skipping (no abstract/title)")
                continue
            
            # Convert to lowercase once
            text_lower = searchable_text.lower()
            
            # OPTIMIZATION: pre-filter keywords based on which ones appear in text as substrings
            # This is much faster than regex, then we validate with regex
            candidate_keywords = set()
            for keyword in self.all_keywords_set:
                # Quick substring check first (very fast)
                if keyword in text_lower:
                    candidate_keywords.add(keyword)
            
            # Find ALL keywords that match in this text (only those that passed pre-filter)
            matched_keywords: Set[str] = set()
            for keyword in candidate_keywords:
                if self.keyword_patterns[keyword].search(text_lower):
                    matched_keywords.add(keyword)
            
            if not matched_keywords:
                continue
            
            # Now map matched keywords to emails
            matched_emails: Dict[str, List[str]] = {}
            for keyword in matched_keywords:
                # Get list of emails that have this keyword
                for email in self.keyword_to_emails.get(keyword, []):
                    if email not in matched_emails:
                        matched_emails[email] = []
                    matched_emails[email].append(keyword)
            
            # Filter matched emails based on criteria
            filtered_emails: Dict[str, List[str]] = {}
            for email, keywords in matched_emails.items():
                # Apply per-recipient filtering
                filtered_grants_for_email, stats = self._filter_grants_for_recipient(
                    [grant],
                    email,
                    exclude_already_sent=exclude_already_sent,
                    exclude_failed_extraction=exclude_failed_extraction,
                    exclude_expired_deadline=exclude_expired_deadline
                )
                
                # Track exclusion reasons
                if stats['excluded_already_sent'] > 0:
                    per_recipient_excluded[email]['already_sent'] += 1
                if stats['excluded_failed_extraction'] > 0:
                    per_recipient_excluded[email]['failed'] += 1
                if stats['excluded_expired_deadline'] > 0:
                    per_recipient_excluded[email]['expired'] += 1
                
                # If grant passed filters for this recipient, include it
                if filtered_grants_for_email:
                    filtered_emails[email] = keywords
            
            # If any emails passed filters, add result
            if filtered_emails:
                result = {
                    'grant_index': grant_idx,
                    'url': grant.get('url'),
                    'title': grant.get('title'),
                    'organization': grant.get('organization'),
                    'abstract': grant.get('abstract'),
                    'deadline': grant.get('deadline'),
                    'funding_amount': grant.get('funding_amount'),
                    'extraction_date': grant.get('extraction_date'),
                    'extraction_success': grant.get('extraction_success', True),
                    'extraction_error': grant.get('extraction_error'),
                    'matched_emails': [
                        {
                            'email': email,
                            'matched_keywords': sorted(keywords)
                        }
                        for email, keywords in filtered_emails.items()
                    ]
                }
                results.append(result)
                grants_with_matches += 1
            
            # Log progress every 1000 grants
            if (grant_idx + 1) % 1000 == 0:
                logger.info(f"Processed {grant_idx + 1}/{len(grants)} grants ({grants_with_matches} with matches)")
        
        # Build stats
        filter_stats['grants_with_matches'] = grants_with_matches
        filter_stats['per_recipient_stats'] = per_recipient_excluded
        
        logger.info(f"Matching complete. Found {grants_with_matches} grants with keyword matches")
        return results, grants_with_matches, filter_stats

    def process(
        self,
        grants_file: str,
        keywords_file: str,
        output_file: Optional[str] = None,
        exclude_already_sent: bool = True,
        exclude_failed_extraction: bool = False,
        exclude_expired_deadline: bool = True
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Main processing pipeline: load data, match keywords, save results.
        
        Args:
            grants_file: Path to extracted_grants_*.json file
            keywords_file: Path to keywords.yaml file
            output_file: Path to save results. If None, auto-generates based on timestamp.
            exclude_already_sent: If True, exclude grants already sent to recipients
            exclude_failed_extraction: If True, exclude failed extractions. Otherwise allow retry.
            exclude_expired_deadline: If True, exclude grants with deadline < today
            
        Returns:
            Tuple of (success: bool, output_data: dict or None)
        """
        try:
            # Load keywords
            if not self.load_keywords(keywords_file):
                return False, None
            
            # Load grants
            logger.info(f"Loading grants from {grants_file}...")
            data = load_json(Path(grants_file))
            
            # Handle both formats: dict with "grants" key or direct list
            if isinstance(data, dict):
                if 'grants' not in data:
                    logger.error(f"Invalid grants data: dict provided but no 'grants' key found")
                    return False, None
                grants = data['grants']
                logger.info(f"Extracted grants from 'grants' key in JSON structure")
            elif isinstance(data, list):
                grants = data
            else:
                logger.error(f"Invalid grants data: expected list or dict with 'grants' key, got {type(data)}")
                return False, None
            
            if not grants:
                logger.error(f"No grants found in data")
                return False, None
            
            logger.info(f"Loaded {len(grants)} grants")
            
            # Match keywords to emails
            matched_results, count_with_matches, filter_stats = self.match_grants_to_emails(
                grants,
                exclude_already_sent=exclude_already_sent,
                exclude_failed_extraction=exclude_failed_extraction,
                exclude_expired_deadline=exclude_expired_deadline
            )
            
            # Prepare output
            output_data = {
                'processing_date': datetime.now().isoformat(),
                'grants_file': grants_file,
                'keywords_file': keywords_file,
                'total_grants': len(grants),
                'grants_with_keyword_matches': count_with_matches,
                'match_rate': round(count_with_matches / len(grants) * 100, 2) if grants else 0,
                'total_emails': len(self.keywords_data),
                'filter_settings': {
                    'exclude_already_sent': exclude_already_sent,
                    'exclude_failed_extraction': exclude_failed_extraction,
                    'exclude_expired_deadline': exclude_expired_deadline
                },
                'filter_stats': filter_stats,
                'results': matched_results
            }
            
            # Determine output file if not specified
            if output_file is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_dir = self.config.get_full_path('paths.output_match_keywords_dir')
                output_file = output_dir / f"grants_by_keywords_emails_{timestamp}.json"
            
            # Save results
            logger.info(f"Saving {len(matched_results)} matched grants to {output_file}...")
            save_json(output_data, Path(output_file), indent=2)
            
            # Log filter stats
            logger.info(
                f"✓ Processing complete!\n"
                f"  Total grants: {len(grants)}\n"
                f"  Grants with matches: {count_with_matches} ({output_data['match_rate']}%)\n"
                f"  Emails processed: {len(self.keywords_data)}\n"
                f"  Filtering enabled: already_sent={exclude_already_sent}, failed={exclude_failed_extraction}, "
                f"expired={exclude_expired_deadline}\n"
                f"  Output: {output_file}"
            )
            
            return True, output_data
            
        except Exception as e:
            logger.error(f"Error during processing: {e}", exc_info=True)
            return False, None


def process_grants_by_keywords(
    grants_file: str,
    keywords_file: str,
    output_file: Optional[str] = None,
    config: Optional[Config] = None,
    exclude_already_sent: bool = True,
    exclude_failed_extraction: bool = False,
    exclude_expired_deadline: bool = True
) -> Tuple[bool, Optional[Dict]]:
    """
    Standalone function to process grants by keywords.
    
    Args:
        grants_file: Path to extracted_grants_*.json
        keywords_file: Path to keywords.yaml
        output_file: Path to save results (auto-generated if None)
        config: Configuration object
        exclude_already_sent: If True, exclude grants already sent to recipients
        exclude_failed_extraction: If True, exclude failed extractions
        exclude_expired_deadline: If True, exclude expired deadlines
        
    Returns:
        Tuple of (success: bool, output_data: dict or None)
    """
    matcher = GrantEmailMatcher(config)
    return matcher.process(
        grants_file,
        keywords_file,
        output_file,
        exclude_already_sent=exclude_already_sent,
        exclude_failed_extraction=exclude_failed_extraction,
        exclude_expired_deadline=exclude_expired_deadline
    )
