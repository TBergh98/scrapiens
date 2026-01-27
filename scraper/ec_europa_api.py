import httpx
import time
import logging
import uuid
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
}

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

def fetch_tenders(
    text: str = "*",
    page_size: int = 50,
    max_pages: int = 10,
    max_retries: int = 3,
    backoff_factor: float = 1.5,
) -> list:
    """
    Fetch tenders from the EU API and return the full raw JSON response for each page.
    DO NOT parse or filter the JSON; pass it as-is to downstream logic.
    """
    all_responses = []
    for page in range(1, max_pages + 1):
        body, boundary = build_multipart_payload(text=text, page_size=page_size, page_number=page)
        headers = HEADERS.copy()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        params = {
            "apiKey": "SEDIA",
            "text": text,
            "pageSize": page_size,
            "pageNumber": page
        }
        for attempt in range(max_retries):
            try:
                resp = httpx.post(API_URL, headers=headers, params=params, content=body.encode("utf-8"), timeout=30)
                resp.raise_for_status()
                logger.info(f"Fetched tenders page {page} (status {resp.status_code})")
                all_responses.append(resp.json())
                if not resp.json().get("results") or len(resp.json()["results"]) < page_size:
                    return all_responses
                break
            except Exception as e:
                logger.warning(f"Error fetching page {page} (attempt {attempt+1}): {e}")
                time.sleep(backoff_factor ** attempt)
        else:
            logger.error(f"Failed to fetch page {page} after {max_retries} attempts.")
            break
    return all_responses

def parse_tenders(data: Dict[str, Any]) -> List[ECEuropaTender]:
    tenders = []
    for item in data.get("results", []):
        tender_id = item.get("cftId") or item.get("id") or ""
        title = item.get("title", "")
        description = item.get("description", "")
        url = item.get("url") or item.get("uri")
        tenders.append(ECEuropaTender(tender_id, title, description, url, raw=item))
    return tenders

# Example usage:
# tenders = fetch_tenders("125bfd67-d66e-4e47-ab99-75b17780059a-PIN")
# for t in tenders:
#     print(t.as_dict())
