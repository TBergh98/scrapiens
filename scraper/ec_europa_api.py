import httpx
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text=*&pageSize={page_size}&pageNumber={page_number}"
BOUNDARY = "----WebKitFormBoundary0Rz8rw1vzPzZscZq"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "No-Cache",
    "Connection": "keep-alive",
    "Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
    "Origin": "https://ec.europa.eu",
    "Referer": "https://ec.europa.eu/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
    "X-Requested-With": "XMLHttpRequest",
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

def build_multipart_payload(cft_id: str, languages: List[str] = ["en"]):
    # This function builds the multipart/form-data body as in the cURL
    # Build the JSON string for the query part (do not use Python dicts here)
    query_json = (
        '{"bool":{"must":[{"terms":{"cftId":["' + cft_id + '"]}}]}}'
    )
    languages_json = str(languages).replace("'", '"')
    parts = [
        f"--{BOUNDARY}",
        'Content-Disposition: form-data; name="query"; filename="blob"',
        'Content-Type: application/json',
        '',
        query_json,
        f"--{BOUNDARY}",
        'Content-Disposition: form-data; name="languages"; filename="blob"',
        'Content-Type: application/json',
        '',
        languages_json,
        f"--{BOUNDARY}--",
        ''
    ]
    return "\r\n".join(parts)

def fetch_tenders(
    cft_id: str,
    page_size: int = 50,
    max_pages: int = 10,
    languages: List[str] = ["en"],
    max_retries: int = 3,
    backoff_factor: float = 1.5,
) -> List[ECEuropaTender]:
    results = []
    for page in range(1, max_pages + 1):
        url = API_URL.format(page_size=page_size, page_number=page)
        payload = build_multipart_payload(cft_id, languages)
        for attempt in range(max_retries):
            try:
                resp = httpx.post(url, headers=HEADERS, content=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                tenders = parse_tenders(data)
                results.extend(tenders)
                logger.info(f"Fetched {len(tenders)} tenders from page {page}.")
                if not data.get("results") or len(data["results"]) < page_size:
                    return results
                break
            except Exception as e:
                logger.warning(f"Error fetching page {page} (attempt {attempt+1}): {e}")
                time.sleep(backoff_factor ** attempt)
        else:
            logger.error(f"Failed to fetch page {page} after {max_retries} attempts.")
            break
    return results

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
