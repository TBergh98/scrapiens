import httpx
import time
import logging
import uuid
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urlparse
from datetime import datetime
from dateutil import parser as date_parser

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


@dataclass
class ECGrantItem:
    """Normalized grant/call item from EC Europa API."""
    reference: str          # Unique identifier
    title: str
    url: str               # Deep link
    organization: Optional[str] = None
    abstract: Optional[str] = None
    deadline: Optional[str] = None  # ISO format: YYYY-MM-DD
    funding_amount: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    source_type: str = "ec_europa"  # Metadata tag
    raw: Optional[Dict[str, Any]] = field(default=None, repr=False)  # Keep raw JSON
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to extraction-compatible dict."""
        return {
            "url": self.url,
            "title": self.title,
            "organization": self.organization,
            "abstract": self.abstract,
            "deadline": self.deadline,
            "funding_amount": self.funding_amount,
            "extraction_success": True,
            "extraction_method": "api_json",
            "reference_id": self.reference,
            "source_type": self.source_type,
            "metadata": {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "status": self.status
            }
        }


class ECSourceConfig:
    """Configuration for each EU Europa API source."""
    def __init__(self, source_type: ECSourceType):
        self.source_type = source_type
        self.base_url = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
        
        if source_type == ECSourceType.TENDERS:
            self.api_key = "SEDIA"
        elif source_type == ECSourceType.CALLS_FOR_PROPOSALS:
            self.api_key = "SEDIA"  # ✅ UNIFIED: Both use SEDIA
        else:
            raise ValueError(f"Unknown source type: {source_type}")


class TendersPayloadBuilder:
    """Builds JSON payload for Tenders API."""
    
    @staticmethod
    def build(
        text: str = "***",
        page_size: int = 50,
        page_number: int = 1,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build JSON payload for Tenders API.
        
        Args:
            text: Search query (default: *** for all)
            page_size: Results per page
            page_number: Page number for pagination
            filters: Optional dict with custom filters
        
        Returns:
            JSON-serializable dict for POST body
        """
        payload = {
            "pageSize": page_size,
            "pageNumber": page_number,
            "sortBy": "startDate",
            "sortOrder": "DESC"
        }
        
        if filters:
            payload.update(filters)
        
        return payload


class ProposalsPayloadBuilder:
    """Builds JSON payload for Calls for Proposals API."""
    
    @staticmethod
    def build(
        text: str = "***",
        page_size: int = 50,
        page_number: int = 1,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build JSON payload for Calls for Proposals API.
        
        Maps URL parameters from EC Europa portal to JSON body:
        - status=31094501,31094502,31094503 → status filter (Open calls)
        - sortBy=startDate → sort configuration
        
        Args:
            text: Search query (default: *** for all)
            page_size: Results per page
            page_number: Page number for pagination
            filters: Optional dict with status, type, year filters
        
        Returns:
            JSON-serializable dict for POST body
        """
        # Default filters for "Open" calls (match portal defaults)
        default_status_codes = [31094501, 31094502, 31094503]  # Open statuses
        
        payload = {
            "pageSize": page_size,
            "pageNumber": page_number,
            "sortBy": "startDate",
            "sortOrder": "DESC",
            "filters": {
                "status": filters.get("status", default_status_codes) if filters else default_status_codes
            }
        }
        
        # Add optional filters
        if filters:
            if "type" in filters:
                payload["filters"]["type"] = filters["type"]
            if "year" in filters:
                payload["filters"]["year"] = filters["year"]
            if "sort" in filters:
                payload["sortBy"] = filters["sort"]
        
        return payload

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


# ============================================================================
# NEW JSON-BASED API IMPLEMENTATION (Unified Strategy)
# ============================================================================

def fetch_data_json(
    source_type: ECSourceType = ECSourceType.TENDERS,
    text: str = "***",
    page_size: int = 50,
    page_number: int = 1,
    filters: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Fetch a single page from EC Europa API using JSON POST.
    
    **CRITICAL:** Uses POST method (GET returns 405).
    
    Args:
        source_type: ECSourceType.TENDERS or ECSourceType.CALLS_FOR_PROPOSALS
        text: Search query (default: "***" for all results)
        page_size: Results per page (default: 50)
        page_number: Page number for pagination (1-indexed)
        filters: Optional dict with source-specific filters
        max_retries: Max retry attempts on failure
    
    Returns:
        Dict with structure:
        {
            "results": [{"reference": "...", "title": "...", ...}],
            "totalResults": 1234,
            "pageNumber": 1,
            "pageSize": 50
        }
    
    Raises:
        ValueError: If source_type is invalid
        httpx.HTTPError: On network/API errors after retries
    """
    # Select configuration
    if source_type == ECSourceType.TENDERS:
        payload_builder = TendersPayloadBuilder
    elif source_type == ECSourceType.CALLS_FOR_PROPOSALS:
        payload_builder = ProposalsPayloadBuilder
    else:
        raise ValueError(f"Unknown source type: {source_type}")
    
    config = ECSourceConfig(source_type)
    
    # Build JSON payload using builder
    json_body = payload_builder.build(
        text=text,
        page_size=page_size,
        page_number=page_number,
        filters=filters
    )
    
    # Query parameters (in URL, not body)
    query_params = {
        "apiKey": config.api_key,
        "text": text,
        "pageSize": page_size,
        "pageNumber": page_number
    }
    
    # Headers
    headers = HEADERS.copy()
    headers["Content-Type"] = "application/json"
    
    logger.info(f"📡 Fetching {source_type.value} page {page_number} (pageSize={page_size})")
    logger.debug(f"   Payload: {json.dumps(json_body, indent=2)}")
    
    # Retry loop
    for attempt in range(max_retries):
        try:
            response = httpx.post(
                API_URL,
                params=query_params,
                json=json_body,  # ✅ JSON body (not multipart)
                headers=headers,
                timeout=30
            )
            
            # Check for errors
            if response.status_code == 405:
                logger.error("❌ 405 Method Not Allowed - API requires POST (not GET)")
                raise ValueError("API endpoint requires POST method, not GET")
            
            response.raise_for_status()
            
            result = response.json()
            result_count = len(result.get("results", []))
            logger.info(f"✅ {source_type.value} page {page_number} fetched "
                       f"({result_count} results, status {response.status_code})")
            
            return result
            
        except httpx.HTTPError as e:
            attempt_num = attempt + 1
            logger.warning(f"⚠️  {source_type.value} page {page_number} "
                          f"(attempt {attempt_num}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                wait_time = 1.5 ** attempt  # Exponential backoff
                logger.debug(f"   Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ Failed after {max_retries} attempts")
                raise
    
    return {}


def normalize_ec_item(
    item: Dict[str, Any],
    source_type: ECSourceType
) -> Optional[ECGrantItem]:
    """
    Normalize raw EC API item to ECGrantItem.
    
    Handles field name variations between Tenders and Proposals:
    - reference: cftId, id, reference, refNumber
    - title: title, name, titleTranslated
    - url: url, uri, deeplink
    - deadline: deadlineDate, deadline, submissionDeadline, closeDate
    
    Args:
        item: Raw API result item
        source_type: Source type (for context)
    
    Returns:
        Normalized ECGrantItem or None if critical fields missing
    """
    
    def pick_field(keys: List[str], default: Optional[str] = None) -> Optional[str]:
        """Try multiple field names, return first non-empty."""
        for key in keys:
            if key in item and item[key]:
                value = item[key]
                return str(value) if value is not None else None
        return default
    
    # Extract required fields
    reference = pick_field(["reference", "cftId", "id", "refNumber", "referenceName"])
    
    # For title, try multiple locations including metadata
    title = pick_field(["title", "name", "titleTranslated", "nameTranslated", "summary", "content"])
    
    # Also check in metadata array if available
    if not title and "metadata" in item and isinstance(item.get("metadata"), dict):
        metadata_title = item["metadata"].get("title", [])
        if isinstance(metadata_title, list) and metadata_title:
            title = str(metadata_title[0])
    
    # Required fields validation
    if not (reference and title):
        logger.debug(f"Skipping item - missing reference or title")
        return None
    
    # Extract identifier for portal URL construction
    # The API provides a JSON endpoint URL, we need to extract the identifier
    # and construct the human-readable portal URL
    identifier = None
    
    # Try to get identifier from metadata first (most reliable)
    if "metadata" in item and isinstance(item.get("metadata"), dict):
        identifier_list = item["metadata"].get("identifier", [])
        if isinstance(identifier_list, list) and identifier_list:
            identifier = str(identifier_list[0])
        elif isinstance(identifier_list, str):
            identifier = identifier_list
    
    # Fallback: extract from URL field if available
    if not identifier:
        api_url = pick_field(["url", "uri", "link"])
        if api_url and ".json" in api_url:
            # Extract identifier from URL like: .../topicDetails/IDENTIFIER.json
            identifier = api_url.split("/")[-1].replace(".json", "")
            logger.debug(f"Extracted identifier '{identifier}' from API URL")
    
    # Construct portal URL using identifier (not reference)
    if identifier:
        # Both tenders and proposals use the same portal structure now
        url = f"https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{identifier}"
        logger.debug(f"Constructed portal URL: {url}")
    else:
        # Last resort fallback: use reference (old behavior)
        logger.warning(f"Could not extract identifier for {reference}, using reference as fallback")
        if source_type == ECSourceType.TENDERS:
            url = f"https://ec.europa.eu/growth/tools-databases/public/tender-details/{reference}"
        else:
            url = f"https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{reference}"
    
    # Extract optional fields
    organization = pick_field(["organisation", "organization", "buyerName", "department", "orgName"])
    abstract = pick_field(["description", "shortDescription", "abstract", "summary_text", "descriptionTranslated"])
    funding_amount = pick_field(["budget", "maxGrant", "estimatedValue", "fundingAmount", "projectBudget"])
    
    # Parse dates (with fallback)
    deadline = None
    deadline_raw = pick_field(["deadlineDate", "deadline", "submissionDeadline", "closeDate"])
    
    # Also try metadata
    if not deadline_raw and "metadata" in item and isinstance(item.get("metadata"), dict):
        deadline_list = item["metadata"].get("deadlineDate", [])
        if isinstance(deadline_list, list) and deadline_list:
            deadline_raw = str(deadline_list[0])
    
    if deadline_raw:
        try:
            deadline = date_parser.parse(str(deadline_raw)).strftime('%Y-%m-%d')
        except Exception:
            deadline = deadline_raw
    
    start_date = pick_field(["startDate", "publicationDate", "launchDate"])
    
    # Try metadata for start date
    if not start_date and "metadata" in item and isinstance(item.get("metadata"), dict):
        start_list = item["metadata"].get("startDate", [])
        if isinstance(start_list, list) and start_list:
            start_date = str(start_list[0])
    
    end_date = pick_field(["endDate", "closingDate", "expiryDate"])
    status = pick_field(["status", "state", "phase"])
    
    # Try metadata for status
    if not status and "metadata" in item and isinstance(item.get("metadata"), dict):
        status_list = item["metadata"].get("status", [])
        if isinstance(status_list, list) and status_list:
            status = str(status_list[0])
    
    return ECGrantItem(
        reference=reference,
        title=title,
        url=url,
        organization=organization,
        abstract=abstract,
        deadline=deadline,
        funding_amount=funding_amount,
        start_date=start_date,
        end_date=end_date,
        status=status,
        raw=item
    )


def parse_api_response(
    response: Dict[str, Any],
    source_type: ECSourceType
) -> List[ECGrantItem]:
    """
    Parse API response and normalize items.
    
    Args:
        response: Raw API response dict
        source_type: Source type
    
    Returns:
        List of normalized ECGrantItem objects
    """
    items = []
    results = response.get("results", [])
    
    logger.debug(f"Parsing {len(results)} items from API response")
    
    for i, raw_item in enumerate(results):
        try:
            item = normalize_ec_item(raw_item, source_type)
            if item:
                items.append(item)
        except Exception as e:
            logger.warning(f"Failed to parse item {i}: {e}")
            continue
    
    logger.info(f"Normalized {len(items)}/{len(results)} items")
    return items


def fetch_all_pages_json(
    source_type: ECSourceType = ECSourceType.TENDERS,
    text: str = "***",
    page_size: int = 50,
    max_pages: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> List[ECGrantItem]:
    """
    Fetch all pages from EC Europa API and normalize results.
    
    Implements pagination loop:
    1. Fetch page 1
    2. Calculate total pages from totalResults
    3. Loop: increment pageNumber until reaching max_pages or totalResults
    4. Normalize each item and yield
    
    Args:
        source_type: TENDERS or CALLS_FOR_PROPOSALS
        text: Search query (default: "***" for all)
        page_size: Results per page (default: 50)
        max_pages: Maximum pages to fetch (safety limit)
        filters: Optional source-specific filters
    
    Returns:
        List of normalized ECGrantItem objects
    """
    all_items = []
    
    logger.info(f"🚀 Starting bulk ingestion: {source_type.value} (max {max_pages} pages)")
    
    for page_num in range(1, max_pages + 1):
        logger.info(f"📄 Page {page_num}/{max_pages}")
        
        # Fetch page
        response = fetch_data_json(
            source_type=source_type,
            text=text,
            page_size=page_size,
            page_number=page_num,
            filters=filters
        )
        
        if not response:
            logger.warning(f"Empty response for page {page_num}, stopping")
            break
        
        # Parse and normalize
        page_items = parse_api_response(response, source_type)
        all_items.extend(page_items)
        
        # Check pagination
        total_results = response.get("totalResults", 0)
        results_count = len(response.get("results", []))
        
        logger.info(f"   → {results_count} results (total: {total_results})")
        
        # Stop if we've fetched all results
        if len(all_items) >= total_results or results_count < page_size:
            logger.info(f"✅ Reached end of results (page {page_num})")
            break
        
        # Small delay to be respectful to API
        time.sleep(0.5)
    
    logger.info(f"✅ Ingestion complete: {len(all_items)} total items fetched")
    return all_items


def fetch_tenders_bulk(
    text: str = "***",
    max_pages: int = 10
) -> List[ECGrantItem]:
    """Convenience wrapper for bulk tender fetching."""
    return fetch_all_pages_json(
        source_type=ECSourceType.TENDERS,
        text=text,
        max_pages=max_pages
    )


def fetch_proposals_bulk(
    text: str = "***",
    max_pages: int = 25,
    status_filter: Optional[List[int]] = None
) -> List[ECGrantItem]:
    """
    Convenience wrapper for bulk proposal fetching.
    
    Defaults to "Open" proposals (matching portal defaults).
    
    Args:
        text: Search query
        max_pages: Max pages (default: 25 matches portal)
        status_filter: Custom status codes (None = open calls)
    
    Returns:
        List of ECGrantItem objects
    """
    filters = {}
    if status_filter:
        filters["status"] = status_filter
    
    return fetch_all_pages_json(
        source_type=ECSourceType.CALLS_FOR_PROPOSALS,
        text=text,
        max_pages=max_pages,
        filters=filters
    )


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
