#!/usr/bin/env python3
"""
Test runner - Scrapes only 100 pages for validation
"""

import sys
from scraper import CWCkiScraper
from analyzer import CWCkiAnalyzer
from pathlib import Path

def main():
    print("="*80)
    print(" CWCki Test Run - 100 Pages")
    print("="*80)
    print("\nThis will:")
    print("  1. Scrape the first 100 pages from CWCki")
    print("  2. Analyze them with AI")
    print("  3. Generate test timeline and summary")
    print("\nEstimated time: 15-20 minutes")
    print("Estimated cost: $2-5")
    
    # Step 1: Scrape first 100 pages
    print("\n[Step 1/2] Scraping first 100 pages...")
    print("-"*80)
    
    scraper = CWCkiScraper()
    
    # Use the built-in scrape function with max_pages limit
    output_dir = "scraped_data_test"
    summary = scraper.scrape_all_pages(output_dir=output_dir, max_pages=100)
    
    print(f"\nScraping complete! Successfully scraped {summary['successful']}/{summary['total_pages']} pages")
    
    # Step 2: Analyze with AI
    print("\n[Step 2/2] Analyzing with AI...")
    print("-"*80)
    
    analyzer = CWCkiAnalyzer(scraped_data_dir=output_dir)
    
    try:
        print("Generating timeline...")
        timeline = analyzer.generate_timeline(output_file="test_timeline.json")
        
        print("Generating summary...")
        summary = analyzer.generate_summary(output_file="test_summary.md")
        
        print("\n" + "="*80)
        print(" TEST COMPLETE!")
        print("="*80)
        print(f"\nTest outputs in: {output_dir}/")
        print("  - test_timeline.json")
        print("  - test_timeline.md")
        print("  - test_summary.md")
        print("\nReview these files to validate the system works correctly.")
        print("If satisfied, run the full scrape with: python run.py")
        
    except Exception as e:
        print(f"\nError during analysis: {e}")
        print("\nMake sure AWS credentials are configured properly.")
        sys.exit(1)

if __name__ == "__main__":
    main()
