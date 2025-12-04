"""Tests for Excel reader module."""

import pytest
from pathlib import Path
from scraper.excel_reader import sanitize_domain_name, read_sites_from_xlsx


def test_sanitize_domain_name():
    """Test domain name sanitization."""
    assert sanitize_domain_name('https://example.com/path') == 'example_com'
    assert sanitize_domain_name('https://sub.example.com') == 'sub_example_com'
    assert sanitize_domain_name('http://example.org:8080') == 'example_org_8080'
    assert sanitize_domain_name('invalid-url') == 'invalid_url'


def test_sanitize_domain_name_special_chars():
    """Test sanitization of special characters."""
    assert sanitize_domain_name('https://ex@mple.com') == 'ex_mple_com'
    assert sanitize_domain_name('https://example.com/path?q=1') == 'example_com'


class TestReadSitesFromXlsx:
    """Tests for reading sites from Excel files."""
    
    def test_missing_file(self):
        """Test error handling for missing file."""
        with pytest.raises(FileNotFoundError):
            read_sites_from_xlsx(
                Path('nonexistent.xlsx'),
                row_range=(16, 68)
            )
    
    def test_invalid_sheet_index(self, tmp_path):
        """Test error handling for invalid sheet index."""
        # This test would require creating a mock Excel file
        # For now, we'll skip the implementation
        pass
