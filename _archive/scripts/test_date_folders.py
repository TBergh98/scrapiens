"""Test script to verify date-stamped folder functionality."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import get_config
from utils.run_date_manager import RunDateManager
from datetime import datetime

def test_run_date_manager():
    """Test the run date manager functionality."""
    print("=" * 60)
    print("Testing RunDateManager")
    print("=" * 60)
    
    config = get_config()
    manager = config.run_date_manager
    
    # Test 1: Get current run date for full pipeline
    print("\n--- Test 1: Full Pipeline Run ---")
    run_date = manager.get_current_run_date(is_full_pipeline=True)
    expected = datetime.now().strftime('%Y%m%d')
    print(f"✓ Full pipeline run date: {run_date}")
    print(f"✓ Expected today's date: {expected}")
    assert run_date == expected, "Full pipeline should create today's date folder"
    
    # Test 2: Get run folder path
    print("\n--- Test 2: Run Folder Path ---")
    run_folder = manager.get_run_folder(run_date)
    print(f"✓ Run folder path: {run_folder}")
    assert str(run_date) in str(run_folder), "Path should contain run date"
    
    # Test 3: Get step folder path
    print("\n--- Test 3: Step Folder Path ---")
    step_folder = manager.get_step_folder(run_date, '01_scrape')
    print(f"✓ Step folder path: {step_folder}")
    assert '01_scrape' in str(step_folder), "Path should contain step name"
    
    # Test 4: List existing runs
    print("\n--- Test 4: List Existing Runs ---")
    runs = manager.list_run_dates()
    print(f"✓ Found {len(runs)} existing run(s)")
    for run in runs[:5]:  # Show first 5
        print(f"  - {run}")
    
    # Test 5: Config integration
    print("\n--- Test 5: Config Integration ---")
    config.set_run_date(run_date)
    current = config.get_run_date()
    print(f"✓ Set run date: {current}")
    assert current == run_date, "Config should store run date"
    
    # Test 6: Get dated path from config
    print("\n--- Test 6: Dated Paths from Config ---")
    dated_path = config.get_dated_path('04_extract', run_date)
    print(f"✓ Dated path for 04_extract: {dated_path}")
    assert run_date in str(dated_path), "Dated path should contain run date"
    assert '04_extract' in str(dated_path), "Dated path should contain step name"
    
    # Test 7: Ensure folder creation
    print("\n--- Test 7: Folder Creation ---")
    test_folder = config.ensure_dated_folder('01_scrape', run_date)
    print(f"✓ Created/ensured folder: {test_folder}")
    assert test_folder.exists(), "Folder should exist after ensure"
    
    # Test 8: Run status
    print("\n--- Test 8: Run Status ---")
    if runs:
        latest = runs[0]
        status = manager.get_run_status(latest)
        print(f"✓ Status for run {latest}:")
        for step, exists in status.items():
            symbol = "✓" if exists else "✗"
            print(f"  {symbol} {step}")
    
    # Test 9: Initialize run (simulating individual step)
    print("\n--- Test 9: Initialize Run for Individual Step ---")
    config2 = get_config()
    detected_date = config2.initialize_run(is_full_pipeline=False, step_name='02_deduplicate')
    print(f"✓ Detected run date for step 02_deduplicate: {detected_date}")
    print(f"  (Should reuse {run_date} if 01_scrape exists, or create new)")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    
    # Print summary
    print("\n--- Run Summary ---")
    manager.print_run_summary()

if __name__ == '__main__':
    try:
        test_run_date_manager()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
