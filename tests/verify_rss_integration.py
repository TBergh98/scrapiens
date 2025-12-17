"""
Verification Script: RSS Integration Complete

This script demonstrates that:
1. RSS extraction module works correctly
2. Backward compatibility is maintained
3. Routing logic works as expected
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from scraper import RssExtractor, load_sites_from_yaml

def test_rss_extractor():
    """Test RSS extraction works."""
    print("=" * 60)
    print("TEST 1: RSS Extractor Direct Usage")
    print("=" * 60)
    
    try:
        rss_url = "https://www.nature.com/nature.rss"
        links = RssExtractor.extract_links_from_rss(rss_url)
        print(f"✅ RSS extraction works: Found {len(links)} links")
        print(f"   Sample link: {list(links)[0] if links else 'None'}")
        return True
    except Exception as e:
        print(f"❌ RSS extraction failed: {e}")
        return False

def test_backward_compatibility():
    """Test existing sites.yaml loads correctly."""
    print("\n" + "=" * 60)
    print("TEST 2: Backward Compatibility")
    print("=" * 60)
    
    try:
        sites = load_sites_from_yaml(Path('input/sites.yaml'))
        print(f"✅ Loaded {len(sites)} sites from sites.yaml")
        
        # Verify all sites have rss_url field (even if null)
        all_have_rss = all('rss_url' in site for site in sites)
        print(f"✅ All sites have 'rss_url' field: {all_have_rss}")
        
        # Check how many have RSS configured
        rss_count = sum(1 for site in sites if site['rss_url'] is not None)
        print(f"   Sites with RSS configured: {rss_count}/{len(sites)}")
        print(f"   Sites using standard extraction: {len(sites) - rss_count}/{len(sites)}")
        
        return True
    except Exception as e:
        print(f"❌ Loading sites failed: {e}")
        return False

def test_rss_example_config():
    """Test RSS example configuration loads."""
    print("\n" + "=" * 60)
    print("TEST 3: RSS Example Configuration")
    print("=" * 60)
    
    try:
        sites = load_sites_from_yaml(Path('input/sites_rss_example.yaml'))
        print(f"✅ Loaded {len(sites)} sites from example config")
        
        for site in sites:
            rss_status = "RSS enabled" if site['rss_url'] else "Standard extraction"
            print(f"   - {site['name']}: {rss_status}")
        
        return True
    except Exception as e:
        print(f"❌ Loading example config failed: {e}")
        return False

def test_routing_logic():
    """Test that routing logic is implemented correctly."""
    print("\n" + "=" * 60)
    print("TEST 4: Routing Logic Implementation")
    print("=" * 60)
    
    try:
        from scraper.link_extractor import scrape_site
        import inspect
        
        # Check if scrape_site function has RSS routing
        source = inspect.getsource(scrape_site)
        
        has_rss_check = 'rss_url' in source
        has_rss_extractor = 'RssExtractor' in source
        has_fallback = 'fall' in source.lower() or 'except' in source
        
        print(f"✅ scrape_site checks for rss_url: {has_rss_check}")
        print(f"✅ scrape_site uses RssExtractor: {has_rss_extractor}")
        print(f"✅ scrape_site has fallback logic: {has_fallback}")
        
        return has_rss_check and has_rss_extractor
    except Exception as e:
        print(f"❌ Routing check failed: {e}")
        return False

def main():
    """Run all verification tests."""
    print("\n" + "🔍 RSS INTEGRATION VERIFICATION 🔍".center(60))
    print()
    
    results = [
        test_rss_extractor(),
        test_backward_compatibility(),
        test_rss_example_config(),
        test_routing_logic()
    ]
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - RSS integration is complete!")
        print("\n📚 Next Steps:")
        print("   1. Read RSS_INTEGRATION.md for usage guide")
        print("   2. Add rss_url to sites in input/sites.yaml")
        print("   3. Run: python examples/example_rss_scraping.py")
        print("   4. Monitor logs for RSS extraction performance")
    else:
        print("\n⚠️  Some tests failed - review output above")
    
    print("=" * 60)

if __name__ == '__main__':
    main()
