import json
from datetime import date
from pathlib import Path

import pytest

from processors.mailer import DigestBuilder


def _write_templates(tmp_path: Path):
    (tmp_path / "email_template.html").write_text(
        "{{ email }}|{{ total_grants }}|{{ keywords|join(',') }}|{{ grants|length }}",
        encoding="utf-8",
    )
    (tmp_path / "email_template.txt").write_text(
        "TXT {{ email }} {{ total_grants }}",
        encoding="utf-8",
    )


def test_build_digests_groups_and_enriches(tmp_path: Path):
    _write_templates(tmp_path)

    sample = {
        "results": [
            {
                "grant_index": 0,
                "url": "https://example.com/g1",
                "title": "Bando 1",
                "organization": "Org A",
                "deadline": "2025-12-30",
                "abstract": "Studio A",
                "matched_emails": [
                    {"email": "alice@example.com", "matched_keywords": ["cat", "dog"]},
                    {"email": "bob@example.com", "matched_keywords": ["cat"]},
                ],
            },
            {
                "grant_index": 1,
                "url": "https://example.com/g2",
                "title": "Bando 2",
                "organization": "Org B",
                "deadline": None,
                "abstract": "Studio B",
                "matched_emails": [
                    {"email": "alice@example.com", "matched_keywords": ["bio"]},
                ],
            },
            {
                "grant_index": 2,
                "url": "https://example.com/g3",
                "title": "Bando 3",
                "organization": "Org C",
                "deadline": "2026-01-20",
                "abstract": "Studio C",
                "matched_emails": [
                    {"email": "bob@example.com", "matched_keywords": ["rna"]},
                ],
            },
        ]
    }

    input_file = tmp_path / "grants_by_keywords_emails_20251223_000000.json"
    input_file.write_text(json.dumps(sample), encoding="utf-8")

    builder = DigestBuilder(template_dir=tmp_path, base_dir=tmp_path, current_date=date(2025, 12, 23))
    output_path = tmp_path / "email_digests_test.json"
    output = builder.build_digests(input_file, output_path)

    assert output_path.exists()
    assert output["total_recipients"] == 2
    assert output["total_grants"] == 3

    alice = next(d for d in output["digests"] if d["email"] == "alice@example.com")
    assert alice["total_grants"] == 2
    assert set(alice["keywords"]) == {"bio", "cat", "dog"}
    statuses = {g["deadline_status"] for g in alice["grants"]}
    assert "critical" in statuses or "missing" in statuses

    bob = next(d for d in output["digests"] if d["email"] == "bob@example.com")
    assert bob["total_grants"] == 2
    assert set(bob["keywords"]) == {"cat", "rna"}
    assert any(g["deadline_status"] == "warning" for g in bob["grants"])


def test_find_latest_source_prefers_timestamp(tmp_path: Path):
    older = tmp_path / "grants_by_keywords_emails_20251222_120000.json"
    newer = tmp_path / "grants_by_keywords_emails_20251223_090000.json"
    older.write_text(json.dumps({"results": []}), encoding="utf-8")
    newer.write_text(json.dumps({"results": []}), encoding="utf-8")

    builder = DigestBuilder(template_dir=tmp_path, base_dir=tmp_path)
    latest = builder.find_latest_source(tmp_path)
    assert latest == newer
