#!/usr/bin/env python3
"""
Main runner script for CWCki scraping and analysis
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime
import os

def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(f" {text}")
    print("="*80 + "\n")

def print_step(step_num, total_steps, text):
    """Print a formatted step"""
    print(f"\n[Step {step_num}/{total_steps}] {text}")
    print("-"*80)

def main():
    print_header("CWCki Scraper and Analysis System")
    print("This system will:")
    print("  1. Scrape all pages from the CWCki (https://sonichu.com/cwcki)")
    print("  2. Process and clean the content")
    print("  3. Use AI to analyze and extract timeline events")
    print("  4. Generate a comprehensive biographical summary")
    print("\nEstimated time: 5-8 hours total")
    print("Estimated cost: $20-50 in AWS Bedrock usage")
    
    # Check if running in non-interactive mode (e.g., background process)
    non_interactive = not sys.stdin.isatty() or os.getenv('CWCKI_AUTO_RUN') == '1'
    
    if not non_interactive:
        # Only prompt if interactive
        response = input("\nDo you want to proceed? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Aborted.")
            return
    else:
        print("\n✅ Running in non-interactive mode - proceeding automatically...")
    
    start_time = time.time()
    
    # Import modules
    try:
        from scraper import CWCkiScraper
        from analyzer import CWCkiAnalyzer
        from extract_media import MediaExtractor
    except ImportError as e:
        print(f"\n❌ Error importing modules: {e}")
        print("\nMake sure you've installed all requirements:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    
    # Step 1: Scrape the wiki
    print_step(1, 2, "Scraping CWCki")
    print("This will take approximately 4-6 hours...")
    print("The scraper will fetch all pages.")
    
    try:
        scraper = CWCkiScraper()
        scrape_summary = scraper.scrape_all_pages()
        
        print(f"\n✅ Scraping completed!")
        print(f"   Total pages: {scrape_summary['total_pages']}")
        print(f"   Successful: {scrape_summary['successful']}")
        print(f"   Failed: {scrape_summary['failed']}")
        
        if scrape_summary['failed'] > 0:
            print(f"\n⚠️  Warning: {scrape_summary['failed']} pages failed to scrape")
            print("   See scraped_data/scrape_summary.json for details")
        
    except Exception as e:
        print(f"\n❌ Error during scraping: {e}")
        print("\nTroubleshooting:")
        print("  - Check your internet connection")
        print("  - Verify the CWCki website is accessible")
        print("  - Check scraped_data/ directory for partial results")
        sys.exit(1)
    
    # Step 2: Extract media from scraped pages
    print_step(2, 3, "Extracting Media from Pages")
    print("This will process scraped HTML to:")
    print("  - Download all images from pages")
    print("  - Extract video URLs")
    print("  - Create media index")
    
    try:
        media_extractor = MediaExtractor()
        
        # Check if media already extracted (check both final file and checkpoint)
        media_index_path = Path('scraped_data/media/media_index.json')
        checkpoint_path = Path('scraped_data/media_extraction_checkpoint.json')
        raw_json_dir = Path('scraped_data/raw_json')
        media_already_extracted = False
        
        # Count total pages that should be processed
        total_pages_expected = len(list(raw_json_dir.glob('*.json'))) if raw_json_dir.exists() else 0
        
        # First check if media_index.json already has complete data
        if media_index_path.exists():
            try:
                with open(media_index_path, 'r') as f:
                    existing_data = json.load(f)
                existing_pages = len(existing_data.get('pages', []))
                existing_images = existing_data.get('downloaded_images', 0)
                
                if existing_pages == total_pages_expected and existing_pages > 0 and existing_images > 0:
                    media_already_extracted = True
                    print(f"\n✅ Media already extracted:")
                    print(f"   All {existing_pages}/{total_pages_expected} pages processed")
                    print(f"   Images: {existing_images}")
                    print(f"   Videos: {existing_data.get('total_videos', 0)}")
                    print(f"\n⏭️  Skipping media extraction (complete data found)")
            except Exception as e:
                print(f"\n⚠️  Error reading media_index.json: {e}")
        
        # Check checkpoint file only if media_index.json doesn't have complete data
        if not media_already_extracted and checkpoint_path.exists() and total_pages_expected > 0:
            try:
                with open(checkpoint_path, 'r') as f:
                    checkpoint_data = json.load(f)
                media_entries = checkpoint_data.get('media_index', [])
                checkpoint_pages = len(media_entries)
                
                # Only consider complete if checkpoint has ALL pages
                if checkpoint_pages == total_pages_expected:
                    # Count images and videos
                    total_images = sum(len(page.get('images', [])) for page in media_entries)
                    total_videos = sum(len(page.get('videos', [])) for page in media_entries)
                    
                    media_already_extracted = True
                    print(f"\n✅ Media extraction complete (from checkpoint):")
                    print(f"   All {checkpoint_pages}/{total_pages_expected} pages processed")
                    print(f"   Images: {total_images}")
                    print(f"   Videos: {total_videos}")
                    
                    # CRITICAL: Only finalize if media_index.json doesn't already have better data
                    should_finalize = False
                    if not media_index_path.exists():
                        should_finalize = True
                        print("   media_index.json doesn't exist - will create from checkpoint")
                    else:
                        # Check if existing file needs updating
                        try:
                            with open(media_index_path, 'r') as f:
                                current_data = json.load(f)
                            current_pages = len(current_data.get('pages', []))
                            current_images = current_data.get('downloaded_images', 0)
                            
                            # NEVER overwrite complete data - checkpoint might be stale/incomplete
                            if current_pages >= checkpoint_pages and current_images > 0:
                                print(f"   ⏭️  media_index.json already has complete data:")
                                print(f"      Current: {current_pages} pages, {current_images} images")
                                print(f"      Checkpoint: {checkpoint_pages} pages, {total_images} images")
                                print(f"   Keeping existing file - NOT overwriting with checkpoint!")
                                should_finalize = False
                            elif current_pages == 0 or current_images == 0:
                                # Only overwrite if current file is actually empty
                                print(f"   media_index.json appears empty - will use checkpoint data")
                                should_finalize = True
                            else:
                                print(f"   ⚠️  media_index.json has {current_pages} pages with {current_images} images")
                                print(f"   Checkpoint has {checkpoint_pages} pages with {total_images} images")
                                print(f"   Keeping existing file to be safe")
                                should_finalize = False
                        except Exception as e:
                            print(f"   ⚠️  Error reading media_index.json: {e}")
                            print(f"   Will NOT overwrite to prevent data loss")
                            should_finalize = False
                    
                    if should_finalize:
                        print("   Finalizing media_index.json from checkpoint...")
                        final_data = {
                            'total_pages': len(media_entries),
                            'total_images': total_images,
                            'downloaded_images': total_images,
                            'skipped_images': 0,
                            'total_videos': total_videos,
                            'extracted_at': checkpoint_data.get('last_updated', ''),
                            'pages': media_entries
                        }
                        with open(media_index_path, 'w') as f:
                            json.dump(final_data, f, indent=2)
                        print(f"   ✅ media_index.json created with {len(media_entries)} pages!")
                else:
                    print(f"\n⚠️  Incomplete checkpoint found:")
                    print(f"   Has {checkpoint_pages}/{total_pages_expected} pages")
                    print(f"   Will continue extraction from checkpoint...")
            except Exception as e:
                print(f"\n⚠️  Error reading checkpoint: {e}")
        
        
        if not media_already_extracted:
            print("\nExtracting media from scraped pages...")
            media_data = media_extractor.extract_all_media()
            
            if media_data is None:
                print(f"\n⚠️  Media extraction skipped or failed")
            elif media_data.get('total_pages', 0) == 0:
                print(f"\n⚠️  Media extraction completed but found no pages")
                print("   This might indicate an issue with the raw_json directory")
            else:
                print(f"\n✅ Media extraction completed!")
                print(f"   Pages processed: {media_data.get('total_pages', 0)}")
                print(f"   Images downloaded: {media_data.get('downloaded_images', 0)}")
                print(f"   Videos found: {media_data.get('total_videos', 0)}")
        
    except Exception as e:
        print(f"\n⚠️  Warning: Media extraction failed: {e}")
        print("   Continuing without media...")
    
    # Step 3: Analyze content and generate outputs
    print_step(3, 3, "Analyzing Content with AI")
    print("This will use Strands Agents (Amazon Bedrock with Claude) to:")
    print("  - Extract chronological events")
    print("  - Generate comprehensive timeline")
    print("  - Link media to events")
    print("  - Create biographical summary")
    
    # Check for AWS credentials
    if not any([
        os.getenv('AWS_ACCESS_KEY_ID'),
        os.getenv('AWS_PROFILE'),
        Path.home() / '.aws' / 'credentials'
    ]):
        print("\n⚠️  Warning: AWS credentials not detected!")
        print("   Make sure you have configured AWS credentials.")
        print("   See README.md for setup instructions.")
        
        if not non_interactive:
            response = input("\nDo you want to continue anyway? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("Aborted. Please configure AWS credentials first.")
                return
        else:
            print("\n⚠️  Continuing without detected credentials - relying on environment...")
    
    try:
        analyzer = CWCkiAnalyzer()
        
        # Generate timeline
        print("\nGenerating timeline...")
        timeline = analyzer.generate_timeline()
        
        # Link media to events - skip if already done (checkpoint exists means complete)
        media_index_path = Path('scraped_data/media/media_index.json')
        media_linking_checkpoint = Path('scraped_data/media_linking_checkpoint.json')
        timeline_media_path = Path('scraped_data/timeline_with_media.json')
        
        # Check if media linking already complete
        media_linking_complete = False
        if timeline_media_path.exists() and media_linking_checkpoint.exists():
            try:
                # Both timeline_with_media.json and checkpoint exist = complete
                with open(media_linking_checkpoint, 'r') as f:
                    checkpoint_data = json.load(f)
                checkpoint_events = len(checkpoint_data.get('events_with_media', []))
                
                if checkpoint_events > 0:
                    print(f"\n✅ Media linking already complete")
                    print(f"   Checkpoint exists with {checkpoint_events} events")
                    print(f"   timeline_with_media.json exists")
                    print(f"\n⏭️  Skipping media linking (already done)")
                    media_linking_complete = True
            except Exception as e:
                logger.debug(f"Could not verify media linking completion: {e}")
        
        if not media_linking_complete and media_index_path.exists():
            try:
                with open(media_index_path, 'r') as f:
                    media_data = json.load(f)
                if media_data.get('total_pages', 0) > 0:
                    print("\nLinking media to timeline events...")
                    timeline_with_media = analyzer.link_media_to_events()
                else:
                    print("\n⚠️  Media index is empty, skipping media linking")
            except Exception as e:
                print(f"\n⚠️  Error checking media index: {e}")
        elif not media_linking_complete:
            print("\n⚠️  Media index not found, skipping media linking")
        
        # Generate summary
        print("\nGenerating comprehensive summary...")
        summary = analyzer.generate_summary()
        
        # Generate worst things committed list
        print("\nGenerating top 100 worst things committed list...")
        worst_things = analyzer.generate_worst_things_list()
        
        print(f"\n✅ Analysis completed!")
        
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        print("\nTroubleshooting:")
        print("  - Verify AWS credentials are properly configured")
        print("  - Ensure Claude 4 Sonnet access is enabled in Amazon Bedrock")
        print("  - Check your AWS region supports Bedrock")
        print("  - See README.md for detailed setup instructions")
        sys.exit(1)
    
    # Summary
    elapsed_time = time.time() - start_time
    hours = int(elapsed_time // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    
    print_header("COMPLETE!")
    print(f"Total time: {hours}h {minutes}m")
    print(f"\nOutput files created in: scraped_data/")
    print("  📄 timeline.json              - Structured timeline data")
    print("  📄 timeline_with_media.json   - Timeline with images/videos")
    print("  📄 timeline.md                - Markdown formatted timeline")
    print("  📄 summary.md                 - Comprehensive biographical summary")
    print("  ⚠️  worst_things.md            - Top 100 worst things committed")
    print("  📸 media/images/              - Downloaded images")
    print("  🎥 media/media_index.json     - Media catalog")
    print("\nYou can now:")
    print("  1. Open timeline_viewer_pro.html for visual timeline with worst things list")
    print("  2. Review timeline.md for chronological events")
    print("  3. Read summary.md for comprehensive biography")
    print("  4. Review worst_things.md for top 100 worst things committed")
    print("\nTo view the visual timeline:")
    print("  ./serve_timeline.sh")
    print("  Then open: http://localhost:8000/timeline_viewer_media.html")

if __name__ == "__main__":
    main()