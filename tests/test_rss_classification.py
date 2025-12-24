"""
Test RSS Classification with REGEX-only patterns.

Verifica che:
1. Titolo viene estratto correttamente (fallback chain)
2. Classificazione REGEX funziona su titolo SOLO
3. Fallback a URL happens se no REGEX match
"""

import json
import logging
from pathlib import Path
from processors.classifier import LinkClassifier
from config.settings import get_config

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# RSS feeds to test
RSS_FEEDS = {
    'masaf': 'intermediate_outputs/rss_feeds/masaf_rss.json',
    'nih_grants': 'intermediate_outputs/rss_feeds/nih_grants_rss.json',
    'ec_calls_for_proposals': 'intermediate_outputs/rss_feeds/ec_calls_for_proposals_rss.json',
    'sciencebusiness': 'intermediate_outputs/rss_feeds/sciencebusiness_rss.json',
}


def test_title_extraction():
    """Test _extract_rss_title() on real RSS data"""
    print("\n" + "="*80)
    print("TEST 1: Title Extraction (Fallback Chain)")
    print("="*80)
    
    classifier = LinkClassifier()
    config = get_config()
    
    for feed_name, feed_path in RSS_FEEDS.items():
        print(f"\n[Feed] {feed_name}")
        print(f"   Path: {feed_path}")
        
        try:
            with open(feed_path, 'r', encoding='utf-8') as f:
                entries = json.load(f)
            
            # Test on first 5 entries
            for i, entry in enumerate(entries[:5]):
                title_text, source_field = classifier._extract_rss_title(entry)
                
                status = "[OK]" if title_text else "[FAIL]"
                print(f"\n   Entry {i+1}: {status}")
                print(f"      Source field: {source_field}")
                if title_text:
                    preview = (title_text[:70] + '...') if len(title_text) > 70 else title_text
                    print(f"      Title: {preview}")
                else:
                    print(f"      Available fields: {list(entry.keys())[:5]}")
        
        except FileNotFoundError:
            print(f"   [ERROR] File not found")
        except Exception as e:
            print(f"   [ERROR] {e}")


def test_regex_classification():
    """Test REGEX classification on real RSS titles"""
    print("\n" + "="*80)
    print("TEST 2: REGEX Classification (Title-Only)")
    print("="*80)
    
    classifier = LinkClassifier()
    config = get_config()
    
    # Get patterns from config
    title_patterns = config.get('rss_classification.title_patterns', {})
    
    print(f"\nPatterns loaded from config:")
    for category, patterns in title_patterns.items():
        print(f"\n  {category}: ({len(patterns)} patterns)")
        for pattern in patterns[:3]:  # Show first 3
            print(f"    - {pattern}")
        if len(patterns) > 3:
            print(f"    ... and {len(patterns) - 3} more")
    
    results_by_category = {
        'single_grant': 0,
        'grant_list': 0,
        'other': 0,
        'no_match': 0,
    }
    
    for feed_name, feed_path in RSS_FEEDS.items():
        print(f"\n\n[Feed] {feed_name}")
        
        try:
            with open(feed_path, 'r', encoding='utf-8') as f:
                entries = json.load(f)
            
            # Test on first 10 entries
            for i, entry in enumerate(entries[:10]):
                result = classifier._classify_rss_with_regex(
                    url=entry.get('url', entry.get('link', '')),
                    metadata=entry
                )
                
                if result:
                    category = result['category']
                    reason = result['reason']
                    results_by_category[category] += 1
                    
                    title_text, _ = classifier._extract_rss_title(entry)
                    preview = (title_text[:60] + '...') if len(title_text) > 60 else title_text
                    
                    print(f"\n   Entry {i+1}:")
                    print(f"      [OK] {category.upper()}")
                    print(f"      Title: {preview}")
                    print(f"      Reason: {reason}")
                else:
                    results_by_category['no_match'] += 1
                    title_text, _ = classifier._extract_rss_title(entry)
                    preview = (title_text[:60] + '...') if len(title_text) > 60 else title_text
                    
                    print(f"\n   Entry {i+1}:")
                    print(f"      [FALLBACK] NO REGEX MATCH (will fallback to URL)")
                    print(f"      Title: {preview}")
        
        except FileNotFoundError:
            print(f"   [ERROR] File not found")
        except Exception as e:
            print(f"   [ERROR] {e}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY: REGEX Classification Results")
    print("="*80)
    total = sum(results_by_category.values())
    for category, count in results_by_category.items():
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {category:15s}: {count:3d} ({pct:5.1f}%)")
    print(f"  {'TOTAL':15s}: {total:3d}")


def test_fallback_behavior():
    """Test fallback behavior when RSS classification fails"""
    print("\n" + "="*80)
    print("TEST 3: Fallback Behavior (RSS -> URL-based classification)")
    print("="*80)
    
    classifier = LinkClassifier()
    
    print("\nScenario: Entry with no valid title")
    print("  Expected: _classify_rss_with_regex() returns None")
    print("  Then: Falls back to URL-based classification\n")
    
    test_metadata = {
        'id': 'https://example.com/entry/123',
        'guidislink': False,
        # Missing title, summary, description
    }
    
    result = classifier._classify_rss_with_regex(
        url='https://example.com/entry/123',
        metadata=test_metadata
    )
    
    if result is None:
        print("  [OK] Correctly returned None (will trigger URL-fallback)")
    else:
        print(f"  [FAIL] Should return None but got: {result}")


if __name__ == '__main__':
    print("\n" + "#"*80)
    print("# RSS Classification Test Suite")
    print("#"*80)
    
    try:
        test_title_extraction()
        test_regex_classification()
        test_fallback_behavior()
        
        print("\n" + "#"*80)
        print("# All tests completed!")
        print("#"*80 + "\n")
    
    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
