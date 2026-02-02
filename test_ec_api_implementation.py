#!/usr/bin/env python3
"""
Test script for EC Europa API Unified Ingestion Strategy.
Tests the new fetch_data_json, normalization, and pagination implementations.
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all new modules can be imported."""
    logger.info("=" * 60)
    logger.info("TEST 1: Verify Imports")
    logger.info("=" * 60)
    
    try:
        from scraper.ec_europa_api import (
            ECSourceType,
            ECGrantItem,
            TendersPayloadBuilder,
            ProposalsPayloadBuilder,
            fetch_data_json,
            normalize_ec_item,
            parse_api_response,
            fetch_all_pages_json,
            fetch_tenders_bulk,
            fetch_proposals_bulk
        )
        logger.info("✅ All EC Europa API imports successful")
        
        from processors.extractor import GrantExtractor
        logger.info("✅ GrantExtractor import successful")
        
        # Check if bulk extraction method exists
        if hasattr(GrantExtractor, 'extract_from_ec_api_bulk'):
            logger.info("✅ GrantExtractor.extract_from_ec_api_bulk() method exists")
        else:
            logger.error("❌ GrantExtractor.extract_from_ec_api_bulk() method NOT found")
            return False
        
        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return False


def test_payload_builders():
    """Test payload builder functionality."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Payload Builders")
    logger.info("=" * 60)
    
    try:
        from scraper.ec_europa_api import TendersPayloadBuilder, ProposalsPayloadBuilder
        
        # Test Tenders payload
        tenders_payload = TendersPayloadBuilder.build(
            text="***",
            page_size=50,
            page_number=1
        )
        logger.info(f"✅ Tenders payload built: {tenders_payload}")
        
        # Verify structure
        assert tenders_payload.get("pageSize") == 50
        assert tenders_payload.get("pageNumber") == 1
        assert tenders_payload.get("sortBy") == "startDate"
        logger.info("✅ Tenders payload has correct structure")
        
        # Test Proposals payload
        proposals_payload = ProposalsPayloadBuilder.build(
            text="***",
            page_size=50,
            page_number=1
        )
        logger.info(f"✅ Proposals payload built: {proposals_payload}")
        
        # Verify structure with filters
        assert "filters" in proposals_payload
        assert "status" in proposals_payload["filters"]
        assert proposals_payload["filters"]["status"] == [31094501, 31094502, 31094503]
        logger.info("✅ Proposals payload has correct filter structure")
        
        return True
    except Exception as e:
        logger.error(f"❌ Payload builder test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_normalization():
    """Test ECGrantItem and normalization functions."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Data Normalization")
    logger.info("=" * 60)
    
    try:
        from scraper.ec_europa_api import ECGrantItem, normalize_ec_item, ECSourceType
        
        # Create a sample grant item
        item = ECGrantItem(
            reference="HORIZON-2025-01",
            title="Test Grant",
            url="https://ec.europa.eu/test",
            organization="Test Org",
            abstract="Test abstract",
            deadline="2025-12-31",
            funding_amount="1000000",
            start_date="2025-01-01",
            end_date="2025-12-31",
            status="open"
        )
        
        logger.info(f"✅ ECGrantItem created: {item.reference}")
        
        # Test to_dict conversion
        item_dict = item.to_dict()
        logger.info(f"✅ Item converted to dict with keys: {list(item_dict.keys())}")
        
        # Verify structure
        assert item_dict["url"] == "https://ec.europa.eu/test"
        assert item_dict["extraction_success"] is True
        assert item_dict["extraction_method"] == "api_json"
        logger.info("✅ Item dict has correct structure")
        
        # Test raw item normalization
        raw_item = {
            "cftId": "TEST-001",
            "title": "Test Title",
            "url": "https://ec.europa.eu/test-details",
            "organisation": "Test Org",
            "description": "Test description",
            "deadlineDate": "2025-12-31",
            "budget": "500000"
        }
        
        normalized = normalize_ec_item(raw_item, ECSourceType.TENDERS)
        if normalized:
            logger.info(f"✅ Raw item normalized: {normalized.reference}")
            logger.info(f"   - Title: {normalized.title}")
            logger.info(f"   - URL: {normalized.url}")
        else:
            logger.error("❌ Raw item normalization returned None")
            return False
        
        return True
    except Exception as e:
        logger.error(f"❌ Normalization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cli_command():
    """Verify CLI command is registered."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: CLI Command Registration")
    logger.info("=" * 60)
    
    try:
        from main import cmd_scrape_ec_api
        logger.info("✅ cmd_scrape_ec_api imported successfully")
        
        # Verify it's callable
        assert callable(cmd_scrape_ec_api)
        logger.info("✅ cmd_scrape_ec_api is callable")
        
        return True
    except Exception as e:
        logger.error(f"❌ CLI command test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests and report results."""
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " UNIFIED API INGESTION STRATEGY - IMPLEMENTATION TESTS ".center(58) + "║")
    logger.info("╚" + "=" * 58 + "╝")
    
    tests = [
        ("Imports", test_imports),
        ("Payload Builders", test_payload_builders),
        ("Data Normalization", test_data_normalization),
        ("CLI Command Registration", test_cli_command),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("=" * 60)
    logger.info(f"Results: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        logger.info("\n🎉 All tests passed! Implementation is complete and working.")
        return 0
    else:
        logger.error(f"\n❌ {total_count - passed_count} test(s) failed. Please review.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
