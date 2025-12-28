"""Tests for EC Europa preprocessing integration in extraction pipeline."""

import pytest
from pathlib import Path
from processors.extractor import preprocess_ec_europa_html


class TestPreprocessingIntegration:
    """Test EC Europa HTML preprocessing function."""
    
    @pytest.fixture
    def call_html_content(self):
        """Load call.html sample."""
        sample_path = Path("input/samples/call.html")
        if sample_path.exists():
            with open(sample_path, "r", encoding="utf-8") as f:
                return f.read()
        return None
    
    @pytest.fixture
    def tender_html_content(self):
        """Load tender.html sample."""
        sample_path = Path("input/samples/tender.html")
        if sample_path.exists():
            with open(sample_path, "r", encoding="utf-8") as f:
                return f.read()
        return None
    
    def test_call_template_preprocessing(self, call_html_content):
        """Test preprocessing extracts all 3 cards from CALL template."""
        if not call_html_content:
            pytest.skip("call.html sample not found")
        
        url = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HORIZON-CL1-2025-TWIN-TRANS-01-32"
        result = preprocess_ec_europa_html(call_html_content, url)
        
        assert result is not None, "Preprocessing should return HTML for CALL template"
        assert len(result) < len(call_html_content), "Preprocessed HTML should be smaller"
        assert "General information" in result, "Should contain General information card"
        assert "Topic description" in result, "Should contain Topic description card"
        assert "Topic conditions" in result, "Should contain Topic conditions card"
        
        reduction_pct = (1 - len(result) / len(call_html_content)) * 100
        assert reduction_pct > 90, f"Reduction should be >90%, got {reduction_pct:.1f}%"
        print(f"✓ CALL preprocessing: {len(result)} chars ({reduction_pct:.1f}% reduction)")
    
    def test_tender_template_preprocessing(self, tender_html_content):
        """Test preprocessing extracts General information card from TENDER template."""
        if not tender_html_content:
            pytest.skip("tender.html sample not found")
        
        url = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/TA-2025-TENDER-12345"
        result = preprocess_ec_europa_html(tender_html_content, url)
        
        assert result is not None, "Preprocessing should return HTML for TENDER template"
        assert len(result) < len(tender_html_content), "Preprocessed HTML should be smaller"
        assert "General information" in result, "Should contain General information card"
        
        reduction_pct = (1 - len(result) / len(tender_html_content)) * 100
        assert reduction_pct > 95, f"Reduction should be >95%, got {reduction_pct:.1f}%"
        print(f"✓ TENDER preprocessing: {len(result)} chars ({reduction_pct:.1f}% reduction)")
    
    def test_preprocessing_fallback_non_ec_url(self, call_html_content):
        """Test preprocessing returns None for non-EC Europa URLs."""
        if not call_html_content:
            pytest.skip("call.html sample not found")
        
        url = "https://www.example.com/grant-page"
        result = preprocess_ec_europa_html(call_html_content, url)
        
        # Should return None because URL doesn't match EC Europa pattern
        assert result is None, "Preprocessing should return None for non-EC Europa URLs"
        print("✓ Non-EC URL fallback works correctly")
    
    def test_preprocessing_returns_valid_html(self, call_html_content):
        """Test that preprocessed HTML is valid and contains expected HTML structure."""
        if not call_html_content:
            pytest.skip("call.html sample not found")
        
        url = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/HORIZON-TEST"
        result = preprocess_ec_europa_html(call_html_content, url)
        
        if result:
            assert "<eui-card" in result, "Should contain eui-card elements"
            assert "<div>" in result or "<eui-card" in result, "Should have valid HTML structure"
            assert result.count("<eui-card") > 0, "Should extract at least one card"
            print(f"✓ Preprocessed HTML is valid with {result.count('<eui-card')} cards")


class TestPreprocessingReductionMetrics:
    """Test HTML size reduction metrics."""
    
    def test_call_reduction_metrics(self):
        """Verify CALL preprocessing achieves significant size reduction."""
        sample_path = Path("input/samples/call.html")
        if not sample_path.exists():
            pytest.skip("call.html sample not found")
        
        with open(sample_path, "r", encoding="utf-8") as f:
            html = f.read()
        
        original_size = len(html)
        url = "https://ec.europa.eu/info/funding-tenders/opportunities/topic-details/TEST"
        preprocessed = preprocess_ec_europa_html(html, url)
        
        if preprocessed:
            preprocessed_size = len(preprocessed)
            reduction = (1 - preprocessed_size / original_size) * 100
            
            # Log metrics
            print(f"\nCALL Preprocessing Metrics:")
            print(f"  Original:     {original_size:,} chars")
            print(f"  Preprocessed: {preprocessed_size:,} chars")
            print(f"  Reduction:    {reduction:.1f}%")
            
            assert reduction > 90, "Should achieve >90% reduction"
    
    def test_tender_reduction_metrics(self):
        """Verify TENDER preprocessing achieves maximum size reduction."""
        sample_path = Path("input/samples/tender.html")
        if not sample_path.exists():
            pytest.skip("tender.html sample not found")
        
        with open(sample_path, "r", encoding="utf-8") as f:
            html = f.read()
        
        original_size = len(html)
        url = "https://ec.europa.eu/info/funding-tenders/opportunities/tender-details/TEST"
        preprocessed = preprocess_ec_europa_html(html, url)
        
        if preprocessed:
            preprocessed_size = len(preprocessed)
            reduction = (1 - preprocessed_size / original_size) * 100
            
            # Log metrics
            print(f"\nTENDER Preprocessing Metrics:")
            print(f"  Original:     {original_size:,} chars")
            print(f"  Preprocessed: {preprocessed_size:,} chars")
            print(f"  Reduction:    {reduction:.1f}%")
            
            assert reduction > 95, "Should achieve >95% reduction"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
