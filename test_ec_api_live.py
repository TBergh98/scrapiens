#!/usr/bin/env python3
"""
Live test of EC Europa API - Bulk Ingestion
Tests fetching actual data from the API
"""

import logging
import json
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_live_api_call():
    """Test actual API call to EC Europa."""
    logger.info("=" * 70)
    logger.info("LIVE API TEST: Fetching real data from EC Europa API")
    logger.info("=" * 70)
    
    try:
        from scraper.ec_europa_api import (
            fetch_proposals_bulk,
            ECSourceType,
            fetch_data_json
        )
        
        # Test 1: Single page fetch (light test)
        logger.info("\n📡 TEST 1: Fetching single page (Proposals)")
        logger.info("-" * 70)
        
        response = fetch_data_json(
            source_type=ECSourceType.CALLS_FOR_PROPOSALS,
            text="***",
            page_size=5,  # Small page for testing
            page_number=1
        )
        
        if response:
            logger.info(f"✅ Response received")
            logger.info(f"   - Total Results: {response.get('totalResults', 'N/A')}")
            logger.info(f"   - Page Number: {response.get('pageNumber', 'N/A')}")
            logger.info(f"   - Results in page: {len(response.get('results', []))}")
            
            # Show first result
            if response.get('results'):
                first = response['results'][0]
                title = first.get('title', first.get('summary', 'N/A'))
                title_str = str(title)[:60] if title else 'N/A'
                url_str = str(first.get('url', 'N/A'))[:70]
                logger.info(f"\n   First item:")
                logger.info(f"   - Reference: {first.get('reference', 'N/A')}")
                logger.info(f"   - Title: {title_str}...")
                logger.info(f"   - URL: {url_str}...")
        else:
            logger.error("❌ No response from API")
            return False
        
        # Test 2: Bulk fetch with normalization (max 2 pages)
        logger.info("\n📡 TEST 2: Bulk fetch with normalization (2 pages)")
        logger.info("-" * 70)
        
        items = fetch_proposals_bulk(max_pages=2)
        
        logger.info(f"✅ Bulk fetch complete")
        logger.info(f"   - Total items fetched: {len(items)}")
        
        if items:
            first_item = items[0]
            logger.info(f"\n   First normalized item:")
            logger.info(f"   - Reference: {first_item.reference}")
            logger.info(f"   - Title: {first_item.title[:60]}...")
            logger.info(f"   - URL: {first_item.url[:70]}...")
            logger.info(f"   - Deadline: {first_item.deadline}")
            logger.info(f"   - Organization: {first_item.organization}")
            
            # Test to_dict conversion
            item_dict = first_item.to_dict()
            logger.info(f"\n   Dict keys: {list(item_dict.keys())}")
        else:
            logger.error("❌ No items returned from bulk fetch")
            return False
        
        # Test 3: Test Tenders API
        logger.info("\n📡 TEST 3: Fetching Tenders (single page)")
        logger.info("-" * 70)
        
        from scraper.ec_europa_api import fetch_tenders_bulk
        
        tender_items = fetch_tenders_bulk(max_pages=1)
        
        logger.info(f"✅ Tenders fetch complete")
        logger.info(f"   - Total tenders fetched: {len(tender_items)}")
        
        if tender_items:
            first_tender = tender_items[0]
            logger.info(f"\n   First tender item:")
            logger.info(f"   - Reference: {first_tender.reference}")
            logger.info(f"   - Title: {first_tender.title[:60]}...")
            logger.info(f"   - URL: {first_tender.url[:70]}...")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ ALL LIVE TESTS PASSED!")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_live_api_call()
    exit(0 if success else 1)
