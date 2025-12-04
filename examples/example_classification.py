"""
Example: Link classification with OpenAI.

This example demonstrates how to classify links using the OpenAI API
to determine if they are research grant pages.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from processors import LinkClassifier
from utils import setup_logger, save_json

# Setup logging
logger = setup_logger('example_classification')


def main():
    """Classify a list of links using OpenAI."""
    
    # Sample links to classify
    links = [
        'https://example.com/grants/research-funding-2024',
        'https://example.com/grants/innovation-award',
        'https://example.com/grants/list',
        'https://example.com/about-us',
        'https://example.com/contact',
        'https://example.org/calls/all',
        'https://example.org/calls/doctoral-fellowship',
        'https://example.net/home'
    ]
    
    logger.info(f"Classifying {len(links)} links")
    
    # Create classifier
    # Note: Make sure OPENAI_API_KEY is set in your .env file
    classifier = LinkClassifier()
    
    # Classify links
    results = classifier.classify_links(
        links=links,
        batch_size=10  # Process in batches of 10
    )
    
    # Print results
    print("\n=== Classification Results ===\n")
    
    for result in results:
        print(f"URL: {result['url']}")
        print(f"Category: {result['category']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Reason: {result['reason']}")
        print("-" * 80)
    
    # Count by category
    categories = {}
    for result in results:
        cat = result['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\n=== Summary ===")
    for category, count in categories.items():
        print(f"{category}: {count}")
    
    # Save results
    output_file = Path('output') / 'classification_results.json'
    save_json({'classifications': results, 'summary': categories}, output_file)
    logger.info(f"Results saved to {output_file}")


if __name__ == '__main__':
    main()
