#!/usr/bin/env python3
"""
CWCki Web Scraper
Scrapes all pages from the CWCki using HTML crawling with comprehensive retry logic
Includes media (images and videos) extraction
"""

import requests
import json
import time
import re
import logging
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib.parse import urljoin, urlparse, unquote

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CWCkiScraper:
    def __init__(self, base_url: str = "https://sonichu.com/cwcki"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CWCki Research Bot/1.0 (Educational Purpose)'
        })
        self.rate_limit_delay = 1  # 1 second between requests
        self.max_retries = 3  # Reduced retries for faster failure
        self.retry_delay = 5  # Initial retry delay in seconds
        self.visited_urls: Set[str] = set()
        self.discovered_pages: Dict[str, str] = {}  # url -> title mapping
        self.max_image_size = 10 * 1024 * 1024  # 10MB max per image
        
    def _make_request(self, url: str, retry_count: int = 0) -> Optional[requests.Response]:
        """Make HTTP request with comprehensive retry logic and exponential backoff"""
        time.sleep(self.rate_limit_delay)
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response
            
        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout fetching {url} (attempt {retry_count + 1}/{self.max_retries})")
            return self._retry_request(url, retry_count, e)
            
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error for {url} (attempt {retry_count + 1}/{self.max_retries})")
            return self._retry_request(url, retry_count, e)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [429, 500, 502, 503, 504]:  # Retryable errors
                logger.warning(f"HTTP {e.response.status_code} for {url} (attempt {retry_count + 1}/{self.max_retries})")
                return self._retry_request(url, retry_count, e)
            else:
                logger.error(f"HTTP {e.response.status_code} for {url}: Not retrying")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return self._retry_request(url, retry_count, e)
    
    def _retry_request(self, url: str, retry_count: int, error: Exception) -> Optional[requests.Response]:
        """Handle retry logic with exponential backoff"""
        if retry_count < self.max_retries:
            # Exponential backoff: 2, 4, 8, 16, 32 seconds
            delay = self.retry_delay * (2 ** retry_count)
            logger.info(f"Retrying in {delay} seconds...")
            time.sleep(delay)
            return self._make_request(url, retry_count + 1)
        else:
            logger.error(f"Max retries ({self.max_retries}) exceeded for {url}")
            return None
    
    def _is_valid_wiki_url(self, url: str) -> bool:
        """Check if URL is a valid CWCki page"""
        parsed = urlparse(url)
        # Must be on the same domain and be a wiki page
        return (
            'sonichu.com' in parsed.netloc and
            '/cwcki/' in parsed.path and
            ':' not in parsed.path.split('/')[-1] and  # Exclude special pages
            '#' not in url and  # Exclude anchors
            'action=' not in url and  # Exclude action URLs
            'Special:' not in url and
            'File:' not in url and
            'Category:' not in url and
            'Template:' not in url
        )
    
    def _save_discovery_checkpoint(self, checkpoint_file: Path, to_visit: List[str]):
        """Save current discovery progress to checkpoint file"""
        checkpoint_data = {
            'discovered_pages': self.discovered_pages,
            'visited_urls': list(self.visited_urls),
            'to_visit_queue': to_visit[:500],  # Save first 500 URLs to visit
            'last_updated': datetime.now().isoformat(),
            'total_discovered': len(self.discovered_pages)
        }
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
        logger.info(f"📝 Checkpoint saved: {len(self.discovered_pages)} pages discovered")
    
    def _load_discovery_checkpoint(self, checkpoint_file: Path) -> Optional[List[str]]:
        """Load discovery progress from checkpoint file, returns to_visit queue"""
        if not checkpoint_file.exists():
            return None
        
        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            self.discovered_pages = checkpoint_data['discovered_pages']
            self.visited_urls = set(checkpoint_data['visited_urls'])
            to_visit = checkpoint_data.get('to_visit_queue', [])
            
            logger.info(f"✅ Resumed from checkpoint:")
            logger.info(f"   Pages discovered: {len(self.discovered_pages)}")
            logger.info(f"   URLs visited: {len(self.visited_urls)}")
            logger.info(f"   Queue size: {len(to_visit)}")
            logger.info(f"   Last checkpoint: {checkpoint_data['last_updated']}")
            return to_visit
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    
    def discover_all_pages(self, start_url: str = None, max_pages: int = 3000, checkpoint_interval: int = 50) -> List[str]:
        """Crawl the wiki to discover all pages with checkpoint/resume support"""
        if start_url is None:
            start_url = self.base_url
        
        # Check for existing checkpoint
        checkpoint_file = Path('discovery_checkpoint.json')
        to_visit = self._load_discovery_checkpoint(checkpoint_file)
        
        if to_visit is None:
            logger.info(f"Starting fresh discovery from: {start_url}")
            to_visit = [start_url]
        else:
            logger.info(f"▶️  Resuming discovery from checkpoint")
            # If queue is empty but we have discovered pages, add one to continue
            if not to_visit and self.discovered_pages:
                to_visit = [list(self.discovered_pages.keys())[0]]
        
        pages_since_checkpoint = 0
        
        with tqdm(desc="Discovering pages", total=max_pages, initial=len(self.discovered_pages)) as pbar:
            while to_visit and len(self.discovered_pages) < max_pages:
                url = to_visit.pop(0)
                
                if url in self.visited_urls:
                    continue
                
                self.visited_urls.add(url)
                response = self._make_request(url)
                
                if not response:
                    continue
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Extract page title
                title_elem = soup.find('h1', class_='firstHeading') or soup.find('h1')
                if title_elem:
                    title = title_elem.get_text().strip()
                    if url not in self.discovered_pages:
                        self.discovered_pages[url] = title
                        pbar.update(1)
                        pbar.set_postfix({'pages': len(self.discovered_pages)})
                        pages_since_checkpoint += 1
                
                # Find all wiki links
                content_div = soup.find('div', id='mw-content-text') or soup.find('div', id='content')
                if content_div:
                    links = content_div.find_all('a', href=True)
                    for link in links:
                        href = link['href']
                        full_url = urljoin(url, href)
                        
                        if self._is_valid_wiki_url(full_url) and full_url not in self.visited_urls:
                            to_visit.append(full_url)
                
                # Save checkpoint periodically
                if pages_since_checkpoint >= checkpoint_interval:
                    self._save_discovery_checkpoint(checkpoint_file, to_visit)
                    pages_since_checkpoint = 0
        
        # Final checkpoint save
        self._save_discovery_checkpoint(checkpoint_file, to_visit)
        
        logger.info(f"\n✅ Discovery complete: {len(self.discovered_pages)} pages total")
        return list(self.discovered_pages.keys())
    
    def extract_media_from_page(self, soup: BeautifulSoup, page_url: str) -> Tuple[List[Dict], List[Dict]]:
        """Extract images and video URLs from page"""
        images = []
        videos = []
        
        content_div = soup.find('div', id='mw-content-text') or soup.find('div', id='bodyContent')
        if not content_div:
            return images, videos
        
        # Extract images
        for img in content_div.find_all('img'):
            src = img.get('src', '')
            if src:
                # Make absolute URL
                img_url = urljoin(page_url, src)
                # Get alt text and caption
                alt_text = img.get('alt', '')
                title = img.get('title', '')
                
                # Check if it's in a figure with caption
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
        
        # Extract videos (YouTube embeds, etc.)
        # Look for iframe embeds
        for iframe in content_div.find_all('iframe'):
            src = iframe.get('src', '')
            if 'youtube' in src or 'youtu.be' in src:
                videos.append({
                    'type': 'youtube',
                    'url': src,
                    'embed_url': src
                })
        
        # Look for video tags
        for video in content_div.find_all('video'):
            src = video.get('src', '')
            if src:
                videos.append({
                    'type': 'video',
                    'url': urljoin(page_url, src),
                    'poster': video.get('poster', '')
                })
        
        return images, videos
    
    def download_image(self, img_url: str, output_path: Path) -> bool:
        """Download a single image with size check"""
        try:
            response = self._make_request(img_url)
            if not response:
                return False
            
            # Check size
            content_length = int(response.headers.get('content-length', 0))
            if content_length > self.max_image_size:
                logger.info(f"Skipping large image ({content_length/1024/1024:.1f}MB): {img_url}")
                return False
            
            # Save image
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
            
        except Exception as e:
            logger.warning(f"Failed to download image {img_url}: {e}")
            return False
    
    def get_page_content(self, url: str) -> Optional[Dict]:
        """Fetch full content and metadata for a page including media"""
        response = self._make_request(url)
        if not response:
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Extract title
        title_elem = soup.find('h1', class_='firstHeading') or soup.find('h1')
        title = title_elem.get_text().strip() if title_elem else self.discovered_pages.get(url, url)
        
        # Extract main content
        content_div = soup.find('div', id='mw-content-text') or soup.find('div', id='bodyContent')
        html_content = str(content_div) if content_div else ""
        
        # Extract categories
        categories = []
        cat_div = soup.find('div', id='mw-normal-catlinks')
        if cat_div:
            cat_links = cat_div.find_all('a')
            categories = [link.get_text() for link in cat_links if link.get_text() != 'Categories']
        
        # Extract internal links
        links = []
        if content_div:
            for link in content_div.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)
                if self._is_valid_wiki_url(full_url):
                    link_text = link.get_text().strip()
                    if link_text:
                        links.append(link_text)
        
        # Extract media
        images, videos = self.extract_media_from_page(soup, url)
        
        return {
            'url': url,
            'title': title,
            'display_title': title,
            'html_content': html_content,
            'categories': categories,
            'links': list(set(links)),  # Remove duplicates
            'images': images,
            'videos': videos,
            'scraped_at': datetime.now().isoformat()
        }
    
    def clean_html_content(self, html: str) -> str:
        """Extract clean text from HTML"""
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def scrape_all_pages(self, output_dir: str = "scraped_data", max_pages: int = 3000):
        """Scrape all pages and save to disk with resume capability"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Create subdirectories
        (output_path / "raw_json").mkdir(exist_ok=True)
        (output_path / "clean_text").mkdir(exist_ok=True)
        
        # Discover all page URLs
        print("\n" + "="*80)
        print("PHASE 1: Discovering all pages")
        print("="*80)
        page_urls = self.discover_all_pages(max_pages=max_pages)
        
        # Save page list
        page_data = {
            'total_pages': len(page_urls),
            'pages': [
                {'url': url, 'title': self.discovered_pages.get(url, url)}
                for url in page_urls
            ]
        }
        with open(output_path / "page_titles.json", 'w', encoding='utf-8') as f:
            json.dump(page_data, f, indent=2, ensure_ascii=False)
        
        # Check for already scraped pages
        existing_files = set(p.stem for p in (output_path / "clean_text").glob("*.txt"))
        logger.info(f"Found {len(existing_files)} already scraped pages")
        
        # Filter to only unscraped URLs
        urls_to_scrape = []
        skipped = 0
        for url in page_urls:
            title = self.discovered_pages.get(url, url)
            safe_filename = re.sub(r'[^\w\s-]', '_', title)[:100]
            if safe_filename not in existing_files:
                urls_to_scrape.append(url)
            else:
                skipped += 1
        
        logger.info(f"Skipping {skipped} already scraped pages")
        logger.info(f"Will scrape {len(urls_to_scrape)} new pages")
        
        # Scrape each page with media
        print("\n" + "="*80)
        print(f"PHASE 2: Scraping {len(urls_to_scrape)} pages with media")
        print(f"(Skipping {skipped} already scraped)")
        print("="*80)
        
        # Create media directory
        media_dir = output_path / "media"
        images_dir = media_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        successful = 0
        failed = []
        media_index = []
        downloaded_images = 0
        skipped_images = 0
        
        for url in tqdm(urls_to_scrape, desc="Scraping pages"):
            try:
                content = self.get_page_content(url)
                
                if content:
                    title = content['title']
                    safe_filename = re.sub(r'[^\w\s-]', '_', title)[:100]
                    
                    # Save raw JSON
                    json_path = output_path / "raw_json" / f"{safe_filename}.json"
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(content, f, indent=2, ensure_ascii=False)
                    
                    # Save clean text
                    clean_text = self.clean_html_content(content['html_content'])
                    text_path = output_path / "clean_text" / f"{safe_filename}.txt"
                    
                    with open(text_path, 'w', encoding='utf-8') as f:
                        f.write(f"Title: {title}\n")
                        f.write(f"URL: {url}\n")
                        f.write(f"Categories: {', '.join(content['categories'])}\n")
                        f.write(f"{'='*80}\n\n")
                        f.write(clean_text)
                    
                    # Download images for this page
                    page_images = []
                    for idx, img_data in enumerate(content.get('images', [])):
                        img_url = img_data['url']
                        # Create unique filename using hash
                        img_hash = hashlib.md5(img_url.encode()).hexdigest()[:12]
                        img_ext = Path(urlparse(img_url).path).suffix or '.jpg'
                        img_filename = f"{safe_filename}_{idx}_{img_hash}{img_ext}"
                        img_path = images_dir / img_filename
                        
                        if self.download_image(img_url, img_path):
                            page_images.append({
                                **img_data,
                                'local_path': str(img_path.relative_to(output_path)),
                                'filename': img_filename
                            })
                            downloaded_images += 1
                        else:
                            skipped_images += 1
                    
                    # Build media index entry
                    media_index.append({
                        'page_title': title,
                        'page_url': url,
                        'safe_filename': safe_filename,
                        'images': page_images,
                        'videos': content.get('videos', [])
                    })
                    
                    successful += 1
                else:
                    failed.append({'url': url, 'error': 'No content returned'})
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Exception scraping '{url}': {error_msg}")
                failed.append({'url': url, 'error': error_msg})
        
        # Save media index - CRITICAL: Only write if we actually scraped pages
        media_index_path = media_dir / "media_index.json"
        should_write_media_index = False
        
        if len(media_index) > 0:
            # We scraped new pages, check if we should write
            should_write_media_index = True
            
            # Safety check: don't overwrite if existing file has more complete data
            if media_index_path.exists():
                try:
                    with open(media_index_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    existing_pages = len(existing_data.get('pages', []))
                    existing_images = existing_data.get('total_images', 0)
                    
                    # Don't overwrite if existing has more or equal complete data
                    if existing_pages >= len(media_index) and existing_images > 0:
                        logger.info(f"\n⚠️  SAFETY: Existing media_index.json has complete data")
                        logger.info(f"   Existing: {existing_pages} pages, {existing_images} images")
                        logger.info(f"   New: {len(media_index)} pages, {downloaded_images} images")
                        logger.info(f"   NOT overwriting to prevent data loss!")
                        should_write_media_index = False
                except Exception as e:
                    logger.warning(f"Could not read existing media_index.json: {e}")
        else:
            # No new pages scraped - NEVER overwrite existing file
            if media_index_path.exists():
                logger.info(f"\n⚠️  No new pages scraped - keeping existing media_index.json")
                should_write_media_index = False
            else:
                # No existing file and no data - write empty file
                should_write_media_index = True
        
        if should_write_media_index:
            with open(media_index_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'total_pages': len(media_index),
                    'total_images': downloaded_images,
                    'skipped_images': skipped_images,
                    'total_videos': sum(len(p['videos']) for p in media_index),
                    'pages': media_index
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"\n✅ Saved media_index.json with {len(media_index)} pages")
        
        logger.info(f"\n📸 Media downloaded:")
        logger.info(f"   Images: {downloaded_images}")
        logger.info(f"   Skipped: {skipped_images}")
        logger.info(f"   Videos found: {sum(len(p['videos']) for p in media_index)}")
        
        # Save detailed summary with failure info
        summary = {
            'total_pages': len(page_urls),
            'successful': successful,
            'failed': len(failed),
            'failed_pages': failed,  # Now includes error details
            'scrape_completed': datetime.now().isoformat(),
            'success_rate': f"{(successful/len(page_urls)*100):.2f}%" if page_urls else "0%"
        }
        
        with open(output_path / "scrape_summary.json", 'w') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # Also save failed pages separately for easy review
        if failed:
            with open(output_path / "failed_pages.json", 'w') as f:
                json.dump(failed, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Scraping complete!")
        logger.info(f"Total pages: {len(page_urls)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {len(failed)}")
        logger.info(f"Success rate: {summary['success_rate']}")
        logger.info(f"Data saved to: {output_path}")
        
        if failed:
            logger.warning(f"Failed pages saved to: {output_path}/failed_pages.json")
        
        return summary

def main():
    scraper = CWCkiScraper()
    scraper.scrape_all_pages()

if __name__ == "__main__":
    main()
