#!/usr/bin/env python3
"""
Extract media from already-scraped pages
Processes raw_json files to download images and extract video URLs
"""

import json
import requests
import hashlib
import re
import time
import sys
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from tqdm import tqdm
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('media_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MediaExtractor:
    def __init__(self, scraped_data_dir: str = "scraped_data"):
        self.data_dir = Path(scraped_data_dir)
        self.raw_json_dir = self.data_dir / "raw_json"
        self.media_dir = self.data_dir / "media"
        self.images_dir = self.media_dir / "images"
        self.max_image_size = 10 * 1024 * 1024  # 10MB
        
        # Create directories
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        # Session for downloads
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CWCki Research Bot/1.0 (Educational Purpose)'
        })
        self.rate_limit_delay = 0.2  # 200ms between pages to avoid overwhelming server
    
    def extract_media_from_html(self, html: str, page_url: str) -> tuple[List[Dict], List[Dict]]:
        """Extract images and videos from HTML content"""
        soup = BeautifulSoup(html, 'lxml')
        images = []
        videos = []
        
        # Extract images
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src and not src.startswith('data:'):
                img_url = urljoin(page_url, src)
                alt_text = img.get('alt', '')
                title = img.get('title', '')
                
                # Get caption if in figure
                caption = ''
                parent = img.find_parent('figure') or img.find_parent('div', class_='thumbinner')
                if parent:
                    caption_elem = parent.find('figcaption') or parent.find('div', class_='thumbcaption')
                    if caption_elem:
                        caption = caption_elem.get_text().strip()
                
                images.append({
                    'url': img_url,
                    'alt_text': alt_text,
                    'title': title,
                    'caption': caption
                })
        
        # Extract videos
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if 'youtube' in src or 'youtu.be' in src:
                videos.append({
                    'type': 'youtube',
                    'url': src,
                    'embed_url': src
                })
        
        for video in soup.find_all('video'):
            src = video.get('src', '')
            if src:
                videos.append({
                    'type': 'video',
                    'url': urljoin(page_url, src),
                    'poster': video.get('poster', '')
                })
        
        return images, videos
    
    def download_image(self, img_url: str, output_path: Path) -> bool:
        """Download image with size check"""
        try:
            response = self.session.get(img_url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Check size
            content_length = int(response.headers.get('content-length', 0))
            if content_length > self.max_image_size:
                logger.debug(f"Skipping large image ({content_length/1024/1024:.1f}MB)")
                return False
            
            # Download
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
            
        except Exception as e:
            logger.debug(f"Download failed: {str(e)[:50]}")
            return False
    
    def extract_all_media(self):
        """Extract media from all scraped pages with checkpoint support"""
        print("\n" + "="*80)
        print("EXTRACTING MEDIA FROM SCRAPED PAGES")
        print("="*80)
        
        # Count total raw JSON files to process
        json_files = list(self.raw_json_dir.glob("*.json"))
        total_pages_to_process = len(json_files)
        
        if total_pages_to_process == 0:
            print("\n⚠️  No raw JSON files found in scraped_data/raw_json/")
            print("   Please run the scraper first to download pages")
            return None
        
        # Check if media_index.json already exists and is complete
        media_index_file = self.media_dir / "media_index.json"
        existing_media_data = None
        has_complete_media_index = False
        
        if media_index_file.exists():
            try:
                print(f"\n🔍 Checking existing media_index.json...")
                print(f"   File path: {media_index_file}")
                print(f"   File exists: {media_index_file.exists()}")
                print(f"   File size: {media_index_file.stat().st_size} bytes")
                
                with open(media_index_file, 'r', encoding='utf-8') as f:
                    existing_media_data = json.load(f)
                
                # Debug: Print what we read
                existing_pages = len(existing_media_data.get('pages', []))
                existing_images = existing_media_data.get('downloaded_images', 0)
                existing_total_pages = existing_media_data.get('total_pages', 0)
                
                print(f"   Data loaded:")
                print(f"     - total_pages field: {existing_total_pages}")
                print(f"     - pages array length: {existing_pages}")
                print(f"     - downloaded_images: {existing_images}")
                print(f"     - Expected total: {total_pages_to_process}")
                
                # Check if it has ALL pages processed AND has actual data
                if existing_pages == total_pages_to_process and existing_pages > 0 and existing_images > 0:
                    has_complete_media_index = True
                    print(f"\n✅ Media extraction already complete!")
                    print(f"   All {existing_pages}/{total_pages_to_process} pages processed")
                    print(f"   Images: {existing_images}")
                    print(f"   Videos: {existing_media_data.get('total_videos', 0)}")
                    print(f"\n⏭️  Skipping media extraction (already done)")
                    return existing_media_data
                elif existing_pages > 0:
                    print(f"\n⚠️  Existing media_index.json has {existing_pages}/{total_pages_to_process} pages")
                    print(f"   Will use checkpoint to continue (NOT re-extract from scratch)")
                    print(f"   Existing data preserved - will only add missing pages")
                else:
                    print(f"\n⚠️  media_index.json found but appears empty:")
                    print(f"   Pages in file: {existing_pages}")
                    print(f"   Images in file: {existing_images}")
                    print(f"   Will start fresh extraction")
            except json.JSONDecodeError as e:
                logger.warning(f"Could not parse media_index.json: {e}")
                print(f"\n⚠️  media_index.json is corrupted (JSON parse error)")
                print(f"   Error: {e}")
                existing_media_data = None
            except Exception as e:
                logger.warning(f"Could not read existing media_index.json: {e}")
                print(f"\n⚠️  Error reading media_index.json: {e}")
                existing_media_data = None
        
        # Checkpoint file
        checkpoint_file = self.data_dir / "media_extraction_checkpoint.json"
        
        # Load checkpoint if exists
        processed_files = set()
        media_index = []
        total_images = 0
        total_videos = 0
        downloaded_images = 0
        skipped_images = 0
        
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)
                media_index = checkpoint.get('media_index', [])
                processed_files = set(checkpoint.get('processed_files', []))
                total_images = checkpoint.get('total_images', 0)
                total_videos = checkpoint.get('total_videos', 0)
                downloaded_images = checkpoint.get('downloaded_images', 0)
                skipped_images = checkpoint.get('skipped_images', 0)
                
                logger.info(f"✅ Resumed from checkpoint:")
                logger.info(f"   Processed: {len(processed_files)} files")
                logger.info(f"   Images: {downloaded_images}")
                logger.info(f"   Videos: {total_videos}")
            except Exception as e:
                logger.warning(f"Could not load checkpoint: {e}")
        
        # Get remaining files (json_files already computed above)
        remaining_files = [f for f in json_files if f.name not in processed_files]
        
        if len(processed_files) > 0:
            print(f"\n✅ RESUMING from checkpoint:")
            print(f"   Total pages: {len(json_files)}")
            print(f"   ✓ Already processed & SKIPPED: {len(processed_files)}")
            print(f"   → Will process remaining: {len(remaining_files)}")
            print(f"   Images downloaded so far: {downloaded_images}")
            print(f"   Videos found so far: {total_videos}")
        else:
            print(f"\nStarting fresh extraction:")
            print(f"   Total pages: {len(json_files)}")
        
        print(f"\n⏩ Skipping first {len(processed_files)} files...")
        print("📥 Processing remaining files...\n")
        
        pages_since_checkpoint = 0
        checkpoint_interval = 50
        
        # Progress bar shows total progress including already-processed
        with tqdm(total=len(json_files), desc="Extracting media",
                 initial=len(processed_files),
                 bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                 unit='page') as pbar:
            
            for json_file in remaining_files:
                # Rate limit to avoid overwhelming server
                time.sleep(self.rate_limit_delay)
                
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        page_data = json.load(f)
                    
                    title = page_data.get('title', '')
                    page_url = page_data.get('url', '')
                    html_content = page_data.get('html_content', '')
                    safe_filename = json_file.stem
                    
                    # Extract media from HTML
                    images, videos = self.extract_media_from_html(html_content, page_url)
                    total_images += len(images)
                    total_videos += len(videos)
                    
                    # Download images
                    page_images = []
                    for idx, img_data in enumerate(images):
                        img_url = img_data['url']
                        
                        # Create unique filename
                        img_hash = hashlib.md5(img_url.encode()).hexdigest()[:12]
                        img_ext = Path(urlparse(img_url).path).suffix or '.jpg'
                        img_filename = f"{safe_filename}_{idx}_{img_hash}{img_ext}"
                        img_path = self.images_dir / img_filename
                        
                        # Download if not exists
                        if not img_path.exists():
                            if self.download_image(img_url, img_path):
                                downloaded_images += 1
                            else:
                                skipped_images += 1
                        else:
                            downloaded_images += 1
                        
                        # Add to page images list
                        page_images.append({
                            **img_data,
                            'local_path': str(img_path.relative_to(self.data_dir)),
                            'filename': img_filename
                        })
                    
                    # Add to index
                    media_index.append({
                        'page_title': title,
                        'page_url': page_url,
                        'safe_filename': safe_filename,
                        'images': page_images,
                        'videos': videos
                    })
                    
                    # Mark as processed
                    processed_files.add(json_file.name)
                    pages_since_checkpoint += 1
                    
                    # Update progress bar
                    pbar.update(1)
                    pbar.set_postfix({'images': downloaded_images, 'videos': total_videos})
                    
                    # Save checkpoint periodically
                    if pages_since_checkpoint >= checkpoint_interval:
                        self._save_checkpoint(checkpoint_file, media_index, processed_files,
                                            total_images, total_videos, downloaded_images, skipped_images)
                        pages_since_checkpoint = 0
                    
                except Exception as e:
                    logger.error(f"Error processing {json_file.name}: {e}")
                    pbar.update(1)
        
        # Final checkpoint save
        self._save_checkpoint(checkpoint_file, media_index, processed_files,
                            total_images, total_videos, downloaded_images, skipped_images)
        
        # Save media index - CRITICAL: Never overwrite complete data
        if len(media_index) > 0:
            index_data = {
                'total_pages': len(media_index),
                'total_images': total_images,
                'downloaded_images': downloaded_images,
                'skipped_images': skipped_images,
                'total_videos': total_videos,
                'extracted_at': datetime.now().isoformat(),
                'pages': media_index
            }
            
            # CRITICAL safety check: Never overwrite complete media_index.json
            media_index_path = self.media_dir / "media_index.json"
            should_write = True
            
            if media_index_path.exists():
                try:
                    with open(media_index_path, 'r', encoding='utf-8') as f:
                        current_data = json.load(f)
                    
                    current_pages = len(current_data.get('pages', []))
                    current_images = current_data.get('downloaded_images', 0)
                    new_pages = len(media_index)
                    new_images = downloaded_images
                    
                    # Don't overwrite if existing file has more OR EQUAL complete data
                    if current_pages >= new_pages and current_images > 0:
                        print(f"\n⚠️  SAFETY: Existing media_index.json has complete data")
                        print(f"   Existing: {current_pages} pages, {current_images} images")
                        print(f"   New data: {new_pages} pages, {new_images} images")
                        print(f"   NOT overwriting to prevent data loss!")
                        should_write = False
                        # Return existing data
                        return current_data
                    elif current_pages > new_pages:
                        print(f"\n⚠️  WARNING: Existing media_index.json has MORE data")
                        print(f"   Existing: {current_pages} pages")
                        print(f"   New data: {new_pages} pages")
                        print(f"   NOT overwriting to prevent data loss!")
                        should_write = False
                        # Return existing data
                        return current_data
                except Exception as e:
                    logger.warning(f"Could not read existing media_index.json for safety check: {e}")
                    # On error reading existing file, proceed with caution
                    pass
            
            if should_write:
                with open(media_index_path, 'w', encoding='utf-8') as f:
                    json.dump(index_data, f, indent=2, ensure_ascii=False)
                print(f"\n✅ Saved media_index.json with {len(media_index)} pages")
        else:
            print("\n⚠️  No pages were processed - media_index.json not modified")
            # Try to return existing data if available
            media_index_path = self.media_dir / "media_index.json"
            if media_index_path.exists():
                try:
                    with open(media_index_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    print("   Existing media_index.json preserved")
                    return existing_data
                except:
                    pass
            print("   Make sure scraping has completed first!")
            return None
        
        print(f"\n{'='*80}")
        print(f"MEDIA EXTRACTION COMPLETE!")
        print(f"{'='*80}")
        print(f"\n📸 Images:")
        print(f"   Found: {total_images}")
        print(f"   Downloaded: {downloaded_images}")
        print(f"   Skipped: {skipped_images}")
        print(f"\n🎥 Videos:")
        print(f"   Found: {total_videos}")
        print(f"\n📁 Saved to: {self.media_dir}")
        print(f"   Media index: {self.media_dir / 'media_index.json'}")
        print(f"   Images: {self.images_dir}")
        
        # Keep checkpoint file to mark completion - allows skipping media linking on reruns
        # The checkpoint serves as a completion marker for run.py
        if checkpoint_file.exists():
            print("\n📝 Checkpoint preserved (marks extraction as complete)")
        
        return index_data
    
    def _save_checkpoint(self, checkpoint_file: Path, media_index: List, processed_files: set,
                        total_images: int, total_videos: int, downloaded_images: int, skipped_images: int):
        """Save extraction checkpoint"""
        checkpoint_data = {
            'media_index': media_index,
            'processed_files': list(processed_files),
            'total_images': total_images,
            'total_videos': total_videos,
            'downloaded_images': downloaded_images,
            'skipped_images': skipped_images,
            'last_updated': datetime.now().isoformat()
        }
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
        
        # Show checkpoint save notification (force flush for tqdm compatibility)
        print(f"\n💾 Checkpoint saved: {len(processed_files)} pages, {downloaded_images} images, {total_videos} videos", flush=True)

if __name__ == "__main__":
    extractor = MediaExtractor()
    extractor.extract_all_media()