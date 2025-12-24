import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from processors.mail_sender import MailSender


@pytest.fixture
def sample_digest(tmp_path: Path) -> dict:
    """Sample email_digests_*.json data."""
    return {
        "processing_date": datetime.now().isoformat(),
        "source_file": "intermediate_outputs/grants_by_keywords_emails_20251223_090000.json",
        "total_recipients": 2,
        "total_grants": 3,
        "digests": [
            {
                "email": "alice@example.com",
                "total_grants": 2,
                "keywords": ["virologia", "epidemiologia"],
                "html_body": "<html>Alice digest</html>",
                "text_body": "Alice digest text",
                "grants": [
                    {
                        "url": "https://example.com/g1",
                        "title": "Bando Virologia",
                        "organization": "Fondazione A",
                        "deadline": "2025-12-30",
                        "matched_keywords": ["virologia"],
                        "deadline_status": "critical",
                        "deadline_label": "Scadenza in 7 giorni",
                    }
                ],
            },
            {
                "email": "bob@example.com",
                "total_grants": 1,
                "keywords": ["ricerca"],
                "html_body": "<html>Bob digest</html>",
                "text_body": "Bob digest text",
                "grants": [],
            },
        ],
    }


def test_send_digests_full_mode(tmp_path: Path, sample_digest: dict):
    """Test sending digests in full mode."""
    digest_file = tmp_path / "email_digests_20251223_090000.json"
    digest_file.write_text(json.dumps(sample_digest), encoding="utf-8")

    sender = MailSender(template_dir=tmp_path, base_dir=tmp_path, dry_run=True)

    summary = sender.send_digests(digest_file, mode="full")

    assert summary["mode"] == "full"
    assert summary["sent"] == 2
    assert summary["failed"] == 0
    assert len(sender.successful_sends) == 2


def test_send_digests_test_mode_with_recipients(tmp_path: Path, sample_digest: dict):
    """Test sending digests in test mode with explicit recipients."""
    digest_file = tmp_path / "email_digests_20251223_090000.json"
    digest_file.write_text(json.dumps(sample_digest), encoding="utf-8")

    sender = MailSender(template_dir=tmp_path, base_dir=tmp_path, dry_run=True)

    test_recipients = ["test@example.com"]
    summary = sender.send_digests(digest_file, mode="test", test_recipients=test_recipients)

    assert summary["mode"] == "test"
    assert summary["sent"] == 1
    assert sender.successful_sends[0] == "test@example.com"


def test_find_latest_digest_by_timestamp(tmp_path: Path):
    """Test finding latest digest by timestamp in filename."""
    older = tmp_path / "email_digests_20251222_090000.json"
    newer = tmp_path / "email_digests_20251223_150000.json"

    older.write_text(json.dumps({"digests": []}), encoding="utf-8")
    newer.write_text(json.dumps({"digests": []}), encoding="utf-8")

    sender = MailSender(template_dir=tmp_path, base_dir=tmp_path)
    latest = sender.find_latest_digest(tmp_path)

    assert latest == newer


def test_send_alert_summary_collects_stats(tmp_path: Path, sample_digest: dict):
    """Test alert summary generation with stats."""
    digest_file = tmp_path / "email_digests_20251223_090000.json"
    digest_file.write_text(json.dumps(sample_digest), encoding="utf-8")

    extracted_file = tmp_path / "extracted_grants_20251223_080000.json"
    extracted_file.write_text(
        json.dumps({
            "grants": [
                {"extraction_success": True},
                {"extraction_success": False},
            ]
        }),
        encoding="utf-8",
    )

    match_file = tmp_path / "grants_by_keywords_emails_20251223_070000.json"
    match_file.write_text(
        json.dumps({
            "total_grants": 2,
            "grants_with_keyword_matches": 2,
            "total_emails": 2,
        }),
        encoding="utf-8",
    )

    sender = MailSender(template_dir=tmp_path, base_dir=tmp_path, dry_run=True)
    sender.successful_sends = ["alice@example.com", "bob@example.com"]

    alert = sender.send_alert_summary(digest_file, extracted_file, match_file)

    assert alert["total_extracted_grants"] == 2
    assert alert["extraction_success"] == 1
    assert alert["extraction_success_rate"] == 50.0
    assert alert["total_recipients"] == 2
    assert alert["successful_sends_count"] == 2


def test_failed_sends_tracked_in_alert(tmp_path: Path, sample_digest: dict):
    """Test that failed sends appear in alert context."""
    digest_file = tmp_path / "email_digests_20251223_090000.json"
    digest_file.write_text(json.dumps(sample_digest), encoding="utf-8")

    sender = MailSender(template_dir=tmp_path, base_dir=tmp_path, dry_run=True)
    sender.failed_sends = [
        {
            "recipient": "fail@example.com",
            "error": "SMTP connection timeout",
            "timestamp": datetime.now().isoformat(),
        }
    ]

    alert = sender.send_alert_summary(digest_file)

    assert alert["failed_sends_count"] == 1
    assert alert["failed_sends"][0]["recipient"] == "fail@example.com"


def test_mime_multipart_construction(tmp_path: Path):
    """Test MIME message construction with HTML and text."""
    sender = MailSender(template_dir=tmp_path, base_dir=tmp_path, dry_run=True)

    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        sender._send_email(
            to="test@example.com",
            subject="Test Subject",
            html_body="<html>Test HTML</html>",
            text_body="Test text",
        )

        # Verify sendmail was called with proper message
        assert mock_server.sendmail.called
        call_args = mock_server.sendmail.call_args
        assert call_args[0][1] == "test@example.com"

        # Verify message contains both HTML and text parts
        message_str = call_args[0][2]
        assert "Test HTML" in message_str
        assert "Test text" in message_str
