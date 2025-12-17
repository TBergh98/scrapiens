"""Quick test to verify sites loading works with new RSS field."""

from pathlib import Path
from scraper import load_sites_from_yaml

sites = load_sites_from_yaml(Path('input/sites.yaml'))
print(f'✅ Loaded {len(sites)} sites successfully')
print(f'✅ First site: {sites[0]["name"]}')
print(f'✅ Has rss_url field: {"rss_url" in sites[0]}')
print(f'✅ rss_url value: {sites[0]["rss_url"]}')

# Verify all required fields present
required_fields = ['name', 'url', 'rss_url', 'js', 'next_selector', 'max_pages', 'pagination_param']
all_have_fields = all(all(field in site for field in required_fields) for site in sites)
print(f'✅ All sites have required fields: {all_have_fields}')
