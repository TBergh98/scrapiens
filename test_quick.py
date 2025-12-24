"""Quick test for EC Europa preprocessing."""
from processors.extractor import preprocess_ec_europa_html
from pathlib import Path

# Test CALL template
print("Testing CALL template...")
html = Path('input/samples/call.html').read_text(encoding='utf-8')
result = preprocess_ec_europa_html(html, 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/test')

if result and 'abstract' in result:
    print(f"✅ Abstract trovato: {len(result['abstract'])} chars")
    print(f"✅ Deadline: {result.get('deadline', 'N/A')}")
    print(f"✅ Title: {result.get('title', 'N/A')[:60]}...")
    print(f"✅ Organization: {result.get('organization', 'N/A')}")
    print(f"\nPrimo pezzo abstract:\n{result['abstract'][:300]}...")
else:
    print("❌ Fallito")

print("\n" + "="*60 + "\n")

# Test TENDER template
print("Testing TENDER template...")
html2 = Path('input/samples/tender.html').read_text(encoding='utf-8')
result2 = preprocess_ec_europa_html(html2, 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/tender-details/test')

if result2 and 'abstract' in result2:
    print(f"✅ Abstract trovato: {len(result2['abstract'])} chars")
    print(f"✅ Deadline: {result2.get('deadline', 'N/A')}")
    print(f"✅ Title: {result2.get('title', 'N/A')[:60] if result2.get('title') else 'N/A'}...")
    print(f"\nPrimo pezzo abstract:\n{result2['abstract'][:300]}...")
else:
    print("❌ Fallito")
