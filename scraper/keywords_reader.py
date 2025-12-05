"""YAML reader module for loading keywords and recipient configurations."""

from pathlib import Path
from typing import Dict, List, Any, Tuple
import yaml
from utils.logger import get_logger

logger = get_logger(__name__)


def load_keywords_from_yaml(yaml_path: Path) -> Dict[str, List[str]]:
    """
    Load keywords configuration from a YAML file.
    
    Args:
        yaml_path: Path to keywords.yaml file
        
    Returns:
        Dictionary mapping email addresses to their list of keywords of interest
        Format: {email: [keyword1, keyword2, ...]}
        
    Raises:
        FileNotFoundError: If YAML file not found
        ValueError: If YAML is malformed or invalid
        
    Example YAML format:
        keywords:
          mario@email.it:
            - biotecnologie
            - ricerca
          anna@email.it:
            - sostenibilità
            - ambiente
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"Keywords YAML file not found: {yaml_path}")
    
    logger.info(f"Loading keywords from YAML: {yaml_path}")
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML file {yaml_path}: {e}")
    
    if not data or 'keywords' not in data:
        raise ValueError(f"YAML file must contain 'keywords' key at root level")
    
    keywords_data = data.get('keywords', {})
    
    if not isinstance(keywords_data, dict):
        raise ValueError(f"'keywords' must be a dictionary, got {type(keywords_data)}")
    
    result = {}
    
    for email, kw_list in keywords_data.items():
        # Validate email format (basic check)
        email = str(email).strip()
        if '@' not in email:
            raise ValueError(f"Invalid email format: {email}")
        
        # Validate keywords list
        if not isinstance(kw_list, list):
            raise ValueError(f"Keywords for {email} must be a list, got {type(kw_list)}")
        
        # Convert keywords to strings and normalize (lowercase)
        keywords = [str(kw).strip().lower() for kw in kw_list]
        
        if not keywords:
            logger.warning(f"No keywords found for {email}")
        
        result[email] = keywords
        logger.debug(f"Loaded keywords for {email}: {keywords}")
    
    if not result:
        logger.warning("No keywords loaded from YAML file")
    else:
        logger.info(f"Successfully loaded keywords for {len(result)} recipients")
    
    return result


def create_keyword_to_recipients_map(keywords_dict: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Create a reverse mapping from keywords to recipients.
    
    Args:
        keywords_dict: Mapping of email to keywords list
        
    Returns:
        Dictionary mapping each keyword to list of emails interested in it
        Format: {keyword: [email1, email2, ...]}
        
    Example:
        >>> kw_dict = {"mario@email.it": ["ricerca", "bio"], "anna@email.it": ["ricerca"]}
        >>> create_keyword_to_recipients_map(kw_dict)
        {'ricerca': ['mario@email.it', 'anna@email.it'], 'bio': ['mario@email.it']}
    """
    reverse_map = {}
    
    for email, keywords in keywords_dict.items():
        for keyword in keywords:
            if keyword not in reverse_map:
                reverse_map[keyword] = []
            if email not in reverse_map[keyword]:
                reverse_map[keyword].append(email)
    
    return reverse_map


def get_recipients_for_keywords(keywords_list: List[str], keyword_to_recipients: Dict[str, List[str]]) -> List[str]:
    """
    Get unique list of recipients interested in any of the given keywords.
    
    Args:
        keywords_list: List of keywords
        keyword_to_recipients: Reverse mapping from keywords to recipients
        
    Returns:
        Unique list of email addresses interested in any keyword from the list
        
    Example:
        >>> k2r = {'ricerca': ['mario@email.it', 'anna@email.it'], 'bio': ['mario@email.it']}
        >>> get_recipients_for_keywords(['ricerca', 'bio'], k2r)
        ['mario@email.it', 'anna@email.it']
    """
    recipients = set()
    
    for keyword in keywords_list:
        keyword_lower = str(keyword).strip().lower()
        if keyword_lower in keyword_to_recipients:
            recipients.update(keyword_to_recipients[keyword_lower])
    
    return sorted(list(recipients))


def validate_keywords_yaml(keywords_dict: Dict[str, List[str]]) -> bool:
    """
    Validate loaded keywords dictionary.
    
    Args:
        keywords_dict: Dictionary of email to keywords
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If any entry is invalid
    """
    if not isinstance(keywords_dict, dict):
        raise ValueError("Keywords must be a dictionary")
    
    for email, keywords in keywords_dict.items():
        if not isinstance(email, str) or '@' not in email:
            raise ValueError(f"Invalid email format: {email}")
        
        if not isinstance(keywords, list):
            raise ValueError(f"Keywords for {email} must be a list, got {type(keywords)}")
        
        for kw in keywords:
            if not isinstance(kw, str):
                raise ValueError(f"Keyword must be string for {email}, got {type(kw)}")
    
    return True
