import httpx
import time
import logging
import uuid
from enum import Enum
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
}

class ECSourceType(Enum):
    """EU Europa API source types."""
    TENDERS = "tenders"
    CALLS_FOR_PROPOSALS = "calls_for_proposals"

class ECSourceConfig:
    """Configuration for each EU Europa API source."""
    def __init__(self, source_type: ECSourceType):
        self.source_type = source_type
        self.base_url = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
        
        if source_type == ECSourceType.TENDERS:
            self.api_key = "SEDIA"
        elif source_type == ECSourceType.CALLS_FOR_PROPOSALS:
            self.api_key = "SEDIA_PERSON"
        else:
            raise ValueError(f"Unknown source type: {source_type}")

class ECEuropaTender:
    def __init__(self, tender_id: str, title: str, description: str, url: Optional[str] = None, raw: Optional[dict] = None):
        self.tender_id = tender_id
        self.title = title
        self.description = description
        self.url = url
        self.raw = raw or {}

    def as_dict(self):
        return {
            "id": self.tender_id,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "raw": self.raw,
        }


def build_multipart_payload(text="*", page_size=50, page_number=1, languages=["en"]):
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    query_json = (
        '{"bool":{"must":[]}}' if text == "*" else
        '{"bool":{"must":[{"query_string":{"query":"' + text + '"}}]}}'
    )
    languages_json = str(languages).replace("'", '"')
    parts = [
        f"--{boundary}",
        'Content-Disposition: form-data; name="query"; filename="blob"',
        'Content-Type: application/json',
        '',
        query_json,
        f"--{boundary}",
        'Content-Disposition: form-data; name="languages"; filename="blob"',
        'Content-Type: application/json',
        '',
        languages_json,
        f"--{boundary}--",
        ''
    ]
    return "\r\n".join(parts), boundary

def fetch_data(
    source_type: ECSourceType = ECSourceType.TENDERS,
    text: str = "*",
    page_size: int = 50,
    page_number: int = 1,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Fetch a single page from EU Europa API.
    
    Args:
        source_type: ECSourceType.TENDERS or ECSourceType.CALLS_FOR_PROPOSALS
        text: Search query (default: "*" for all)
        page_size: Results per page
        page_number: Page number for pagination
        max_retries: Max retry attempts
        
    Returns:
        Raw API JSON response for the page
    """
    config = ECSourceConfig(source_type)
    
    body, boundary = build_multipart_payload(text=text, page_size=page_size, page_number=page_number)
    headers = HEADERS.copy()
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    params = {
        "apiKey": config.api_key,
        "text": text,
        "pageSize": page_size,
        "pageNumber": page_number
    }
    
    for attempt in range(max_retries):
        try:
            resp = httpx.post(API_URL, headers=headers, params=params, content=body.encode("utf-8"), timeout=30)
            resp.raise_for_status()
            logger.info(f"✅ {source_type.value} page {page_number} fetched (status {resp.status_code})")
            return resp.json()
        except Exception as e:
            logger.warning(f"❌ {source_type.value} page {page_number} (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt)
    
    logger.error(f"❌ Failed to fetch {source_type.value} page {page_number} after {max_retries} attempts")
    return {}

def fetch_all_pages(
    source_type: ECSourceType = ECSourceType.TENDERS,
    text: str = "*",
    page_size: int = 50,
    max_pages: int = 10,
) -> list:
    """
    Fetch all pages from EU Europa API.
    
    Args:
        source_type: ECSourceType.TENDERS or ECSourceType.CALLS_FOR_PROPOSALS
        text: Search query
        page_size: Results per page
        max_pages: Maximum pages to fetch
        
    Returns:
        List of raw API JSON responses (one per page)
    """
    all_responses = []
    
    for page_num in range(1, max_pages + 1):
        logger.info(f"Fetching {source_type.value} page {page_num}/{max_pages}")
        
        response = fetch_data(
            source_type=source_type,
            text=text,
            page_size=page_size,
            page_number=page_num
        )
        
        if not response:
            logger.warning(f"No response for page {page_num}, stopping pagination")
            break
        
        all_responses.append(response)
        
        # Check if pagination should stop
        results = response.get("results", [])
        if not results or len(results) < page_size:
            logger.info(f"Reached end of results (page {page_num})")
            break
    
    total = sum(len(r.get("results", [])) for r in all_responses)
    logger.info(f"✅ Completed: {len(all_responses)} pages, {total} total results ({source_type.value})")
    return all_responses

def fetch_tenders(
    text: str = "*",
    page_size: int = 50,
    max_pages: int = 10,
) -> list:
    """
    Convenience wrapper for tenders (backward compatible).
    Fetch all pages of tenders from the EU API.
    """
    return fetch_all_pages(ECSourceType.TENDERS, text, page_size, max_pages)

def fetch_calls_for_proposals(
    text: str = "*",
    page_size: int = 50,
    max_pages: int = 10,
) -> list:
    """
    Fetch all pages of calls for proposals from the EU API.
    """
    return fetch_all_pages(ECSourceType.CALLS_FOR_PROPOSALS, text, page_size, max_pages)

def parse_tenders(data: Dict[str, Any]) -> List[ECEuropaTender]:
    tenders = []
    for item in data.get("results", []):
        tender_id = item.get("cftId") or item.get("id") or ""
        title = item.get("title", "")
        description = item.get("description", "")
        url = item.get("url") or item.get("uri")
        tenders.append(ECEuropaTender(tender_id, title, description, url, raw=item))
    return tenders


def _extract_identifier_from_url(url: str) -> Optional[str]:
    """Return the last non-empty path segment to use as API search text."""
    try:
        parsed = urlparse(url)
        segments = [seg for seg in parsed.path.split('/') if seg]
        if segments:
            return segments[-1]
    except Exception:
        return None
    return None


def fetch_item_by_url(url: str) -> Optional[Dict[str, Any]]:
    """Fetch a single EC Europa item using the search API based on the URL identifier."""
    lower_url = url.lower()
    if "tender-details" in lower_url:
        source_type = ECSourceType.TENDERS
    elif "topic-details" in lower_url:
        source_type = ECSourceType.CALLS_FOR_PROPOSALS
    else:
        return None

    identifier = _extract_identifier_from_url(url)
    if not identifier:
        return None

    response = fetch_data(source_type=source_type, text=identifier, page_size=50, page_number=1)
    results = response.get("results", []) if response else []
    if not results:
        return None

    # Try exact match first
    for item in results:
        candidate_url = (item.get("url") or item.get("uri") or "").lower()
        if identifier.lower() in candidate_url:
            return item

    return results[0]

# Example usage:
# tenders = fetch_tenders("125bfd67-d66e-4e47-ab99-75b17780059a-PIN")
# for t in tenders:
#     print(t.as_dict())
