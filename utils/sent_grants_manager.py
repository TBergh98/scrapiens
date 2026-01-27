"""
Sent Grants History Manager

This module manages persistent tracking of which grants have been successfully sent
to which recipients. This is used to prevent re-sending the same grant to the same
person across different pipeline runs.

Data Structure:
    {
        "url_to_recipients": {
            "https://example.com/grant/1": {
                "user@example.com": {
                    "sent_date": "2025-12-29",
                    "email_delivered": true,
                    "email_id": "msg_20251229_123456"
                }
            }
        },
        "stats": {
            "total_sent_records": 100,
            "unique_urls": 85,
            "total_recipients": 5,
            "last_updated": "2025-12-29T23:10:22"
        }
    }
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from utils.file_utils import ensure_directory, load_json, save_json
from utils.logger import get_logger

logger = get_logger(__name__)


class SentGrantsManager:
    """Manages persistent tracking of sent grants to prevent re-sends."""

    def __init__(self, history_file: Optional[Path] = None):
        """
        Initialize the sent grants manager.

        Args:
            history_file: Path to sent_grants_history.json. If None, uses
                         intermediate_outputs/sent_grants_history.json
        """
        if history_file:
            self.history_file = Path(history_file)
        else:
            # Default location in intermediate_outputs root
            self.history_file = Path("intermediate_outputs") / "sent_grants_history.json"

        # Ensure directory exists
        ensure_directory(self.history_file.parent)

        # Load or initialize history
        self.history = self._load_history()

    def _load_history(self) -> Dict:
        """Load history from file or return empty structure."""
        if self.history_file.exists():
            try:
                history = load_json(str(self.history_file))
                logger.debug(f"Loaded sent grants history from {self.history_file}")
                return history
            except Exception as e:
                logger.warning(f"Failed to load {self.history_file}: {e}. Starting fresh.")

        # Return empty history structure
        return {
            "url_to_recipients": {},
            "stats": {
                "total_sent_records": 0,
                "unique_urls": 0,
                "total_recipients": 0,
                "last_updated": None,
            },
        }

    def _save_history(self) -> None:
        """Save history to file."""
        try:
            # Update stats before saving
            self.history["stats"]["last_updated"] = datetime.now().isoformat()
            self.history["stats"]["unique_urls"] = len(self.history["url_to_recipients"])
            self.history["stats"]["total_recipients"] = self._count_unique_recipients()
            self.history["stats"]["total_sent_records"] = self._count_total_records()

            save_json(str(self.history_file), self.history)
            logger.debug(f"Saved sent grants history to {self.history_file}")
        except Exception as e:
            logger.error(f"Failed to save {self.history_file}: {e}")

    def _count_unique_recipients(self) -> int:
        """Count total unique recipients across all URLs."""
        recipients: Set[str] = set()
        for url_recipients in self.history["url_to_recipients"].values():
            recipients.update(url_recipients.keys())
        return len(recipients)

    def _count_total_records(self) -> int:
        """Count total sent records (URL + recipient combinations)."""
        count = 0
        for url_recipients in self.history["url_to_recipients"].values():
            count += len(url_recipients)
        return count

    def mark_sent(
        self, grant_url: str, recipient_email: str, email_delivered: bool = True, email_id: Optional[str] = None
    ) -> None:
        """
        Mark a grant as sent to a recipient.

        Args:
            grant_url: URL of the grant that was sent
            recipient_email: Email address that received the grant
            email_delivered: Whether the email was successfully delivered (default: True)
            email_id: Optional unique email identifier for tracking
        """
        if grant_url not in self.history["url_to_recipients"]:
            self.history["url_to_recipients"][grant_url] = {}

        self.history["url_to_recipients"][grant_url][recipient_email] = {
            "sent_date": datetime.now().date().isoformat(),
            "email_delivered": email_delivered,
            "email_id": email_id,
        }

        logger.debug(f"Marked grant {grant_url} as sent to {recipient_email}")
        self._save_history()

    def mark_sent_batch(self, records: List[Dict[str, any]]) -> None:
        """
        Mark multiple grants as sent in batch.

        Args:
            records: List of dicts with keys:
                - grant_url: str
                - recipient_email: str
                - email_delivered: bool (default: True)
                - email_id: str (optional)
        """
        for record in records:
            self.mark_sent(
                grant_url=record["grant_url"],
                recipient_email=record["recipient_email"],
                email_delivered=record.get("email_delivered", True),
                email_id=record.get("email_id"),
            )

    def was_sent_to(self, grant_url: str, recipient_email: str) -> bool:
        """
        Check if a grant was already sent (with delivery) to a recipient.

        Args:
            grant_url: URL of the grant to check
            recipient_email: Email address to check

        Returns:
            True if the grant was sent AND delivered to this recipient, False otherwise
        """
        if grant_url not in self.history["url_to_recipients"]:
            return False

        if recipient_email not in self.history["url_to_recipients"][grant_url]:
            return False

        record = self.history["url_to_recipients"][grant_url][recipient_email]
        # Only consider it as "sent" if it was actually delivered
        return record.get("email_delivered", False)

    def get_sent_grants_for_recipient(self, recipient_email: str) -> List[str]:
        """
        Get list of all grant URLs successfully sent to a recipient.

        Args:
            recipient_email: Email address to check

        Returns:
            List of grant URLs that were sent and delivered to this recipient
        """
        sent_urls = []
        for url, recipients in self.history["url_to_recipients"].items():
            if recipient_email in recipients:
                record = recipients[recipient_email]
                if record.get("email_delivered", False):
                    sent_urls.append(url)
        return sent_urls

    def filter_unsent_grants(self, grants: List[Dict], recipient_email: str) -> Tuple[List[Dict], int]:
        """
        Filter out grants that were already sent to a recipient.

        Args:
            grants: List of grant dictionaries (must have 'url' key)
            recipient_email: Email address to filter against

        Returns:
            Tuple of (filtered_grants, num_excluded)
        """
        sent_urls = self.get_sent_grants_for_recipient(recipient_email)
        original_count = len(grants)

        filtered = [g for g in grants if g.get("url") not in sent_urls]
        excluded_count = original_count - len(filtered)

        if excluded_count > 0:
            logger.info(
                f"Filtered out {excluded_count} grants already sent to {recipient_email}. "
                f"Keeping {len(filtered)} new grants."
            )

        return filtered, excluded_count

    def get_stats(self) -> Dict:
        """Get summary statistics of sent grants."""
        return {
            **self.history["stats"],
            "urls": list(self.history["url_to_recipients"].keys()),
        }

    def clear_history(self) -> None:
        """
        Clear all history (WARNING: destructive operation).

        Use with caution - this removes all tracking of sent grants.
        """
        logger.warning("Clearing all sent grants history!")
        self.history = {
            "url_to_recipients": {},
            "stats": {
                "total_sent_records": 0,
                "unique_urls": 0,
                "total_recipients": 0,
                "last_updated": None,
            },
        }
        self._save_history()
