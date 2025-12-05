"""Tests for YAML site and keyword readers."""

from pathlib import Path
import pytest
from scraper.sites_reader import load_sites_from_yaml
from scraper.keywords_reader import load_keywords_from_yaml, create_keyword_to_recipients_map


def test_load_sites_missing_file():
    """Ensure missing sites file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_sites_from_yaml(Path('missing_sites.yaml'))


def test_load_sites_invalid_root(tmp_path):
    """Ensure YAML without 'sites' key raises ValueError."""
    yaml_path = tmp_path / 'sites.yaml'
    yaml_path.write_text("{}", encoding='utf-8')
    with pytest.raises(ValueError):
        load_sites_from_yaml(yaml_path)


def test_load_sites_ok(tmp_path):
    """Load a valid sites YAML and validate defaults."""
    yaml_path = tmp_path / 'sites.yaml'
    yaml_path.write_text(
        """
sites:
  - name: example
    url: https://example.com
    keywords: [bio, ricerca]
        """.strip(),
        encoding='utf-8'
    )

    sites = load_sites_from_yaml(yaml_path)
    assert len(sites) == 1
    site = sites[0]
    assert site['name'] == 'example'
    assert site['url'] == 'https://example.com'
    assert site['js'] is False
    assert site['next_selector'] is None
    assert site['max_pages'] == 1
    assert site['keywords'] == ['bio', 'ricerca']


def test_load_keywords_ok(tmp_path):
    """Load keywords YAML and build reverse mapping."""
    yaml_path = tmp_path / 'keywords.yaml'
    yaml_path.write_text(
        """
keywords:
  mario@email.it:
    - bio
    - ricerca
  anna@email.it:
    - ricerca
        """.strip(),
        encoding='utf-8'
    )

    keywords = load_keywords_from_yaml(yaml_path)
    assert set(keywords.keys()) == {'mario@email.it', 'anna@email.it'}
    assert keywords['mario@email.it'] == ['bio', 'ricerca']

    reverse = create_keyword_to_recipients_map(keywords)
    assert reverse['bio'] == ['mario@email.it']
    assert set(reverse['ricerca']) == {'mario@email.it', 'anna@email.it'}
