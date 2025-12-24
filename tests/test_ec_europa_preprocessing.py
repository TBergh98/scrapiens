"""Test EC Europa HTML preprocessing."""

from pathlib import Path
from processors.extractor import preprocess_ec_europa_html


def test_call_template_preprocessing():
    """Test preprocessing of EC Europa CALL template."""
    # Load sample HTML
    sample_path = Path(__file__).parent.parent / "input" / "samples" / "call.html"
    
    if not sample_path.exists():
        print(f"⚠ Sample file not found: {sample_path}")
        return False
    
    with open(sample_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Test URL (call template)
    url = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HORIZON-CL5-2027-07-D3-28"
    
    # Run preprocessing
    result = preprocess_ec_europa_html(html_content, url)
    
    # Assertions
    assert result is not None, "Preprocessing should return data"
    assert 'abstract' in result, "Should extract abstract"
    assert 'deadline' in result, "Should extract deadline"
    
    # Check abstract content
    assert len(result['abstract']) > 100, "Abstract should be substantial"
    assert 'Expected Outcome' in result['abstract'] or 'Scope' in result['abstract'], \
        "Abstract should contain key sections"
    
    # Check deadline
    assert result['deadline'] is not None, "Should find deadline"
    assert '2027' in result['deadline'], "Deadline should contain year"
    
    # Check other fields
    if 'title' in result:
        assert len(result['title']) > 0, "Title should not be empty"
    
    print(f"\n✅ CALL Template Test Passed:")
    print(f"  - Abstract: {len(result['abstract'])} chars")
    print(f"  - Deadline: {result['deadline']}")
    print(f"  - Title: {result.get('title', 'N/A')}")
    print(f"  - Organization: {result.get('organization', 'N/A')}")
    return True


def test_tender_template_preprocessing():
    """Test preprocessing of EC Europa TENDER template."""
    # Load sample HTML
    sample_path = Path(__file__).parent.parent / "input" / "samples" / "tender.html"
    
    if not sample_path.exists():
        print(f"⚠ Sample file not found: {sample_path}")
        return False
    
    with open(sample_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Test URL (tender template)
    url = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/12345"
    
    # Run preprocessing
    result = preprocess_ec_europa_html(html_content, url)
    
    # Assertions
    assert result is not None, "Preprocessing should return data"
    assert 'abstract' in result, "Should extract abstract"
    
    # Check abstract content
    assert len(result['abstract']) > 100, "Abstract should be substantial"
    
    # Check deadline
    if 'deadline' in result:
        assert result['deadline'] is not None, "Should find deadline"
    
    print(f"\n✅ TENDER Template Test Passed:")
    print(f"  - Abstract: {len(result['abstract'])} chars")
    print(f"  - Deadline: {result.get('deadline', 'N/A')}")
    print(f"  - Title: {result.get('title', 'N/A')}")
    return True


if __name__ == "__main__":
    print("Testing EC Europa preprocessing...")
    success = True
    
    try:
        if not test_call_template_preprocessing():
            success = False
    except Exception as e:
        print(f"❌ CALL template test failed: {e}")
        success = False
    
    try:
        if not test_tender_template_preprocessing():
            success = False
    except Exception as e:
        print(f"❌ TENDER template test failed: {e}")
        success = False
    
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
