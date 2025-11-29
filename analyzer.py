#!/usr/bin/env python3
"""
CWCki Content Analyzer
Uses Strands Agents AI to analyze scraped content and generate timeline and summary
With comprehensive retry logic for API calls
"""

import json
import os
import re
import time
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
from collections import defaultdict
from strands import Agent
from tqdm import tqdm

# Set up logging - only errors to stdout, everything to file
file_handler = logging.FileHandler('analyzer.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)  # Only errors to console
console_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# Suppress strands agent verbose output
logging.getLogger('strands').setLevel(logging.ERROR)
logging.getLogger('botocore').setLevel(logging.ERROR)
logging.getLogger('boto3').setLevel(logging.ERROR)

class CWCkiAnalyzer:
    def __init__(self, scraped_data_dir: str = "scraped_data"):
        self.data_dir = Path(scraped_data_dir)
        self.clean_text_dir = self.data_dir / "clean_text"
        self.agent = Agent()
        self.max_retries = 5
        self.retry_delay = 3  # Initial retry delay in seconds
        
    def load_all_pages(self) -> List[Dict[str, str]]:
        """Load all scraped page content"""
        print("Loading scraped pages...")
        pages = []
        
        for text_file in self.clean_text_dir.glob("*.txt"):
            with open(text_file, 'r', encoding='utf-8') as f:
                content = f.read()
                pages.append({
                    'filename': text_file.stem,
                    'content': content
                })
        
        print(f"Loaded {len(pages)} pages")
        return pages
    
    def analyze_page_batch(self, pages: List[Dict], purpose: str = "events", retry_count: int = 0) -> str:
        """Analyze a batch of pages with comprehensive retry logic"""
        # Combine page content - intelligent content management for context window
        # Claude Sonnet has ~200K token context, ~750K chars
        # Reserve 50K for prompt/response, leaving ~700K for content
        # With batch_size=20, that's ~35K chars per page - much more than before!
        
        combined_content = ""
        max_total_chars = 700000  # Conservative limit for Claude's context
        chars_per_page = max_total_chars // len(pages)  # Distribute evenly
        
        for i, page in enumerate(pages, 1):
            combined_content += f"\n\n{'='*80}\nPAGE {i}: {page['filename']}\n{'='*80}\n"
            
            # Use as much content as we can fit per page
            page_content = page['content']
            if len(page_content) > chars_per_page:
                # Smart truncation: prioritize content with dates and events
                # Take first 60% and last 40% to capture intro and conclusions
                first_part = int(chars_per_page * 0.6)
                last_part = int(chars_per_page * 0.4)
                page_content = page_content[:first_part] + "\n\n[...middle section truncated...]\n\n" + page_content[-last_part:]
            
            combined_content += page_content
        
        if purpose == "events":
            prompt = f"""Analyze the following pages from the CWCki (a wiki about Chris Chan) and extract chronological events.

For each significant event you find:
1. Extract the date (be as specific as possible)
2. Write a brief description (1-2 sentences)
3. Note the source page
4. Identify key people involved

Format your response as JSON:
{{
  "events": [
    {{
      "date": "YYYY-MM-DD or YYYY-MM or YYYY",
      "date_precision": "exact|month|year|approximate",
      "description": "Event description",
      "people": ["Person1", "Person2"],
      "source": "Page name",
      "category": "Category (e.g., Personal Life, Internet, Legal, etc.)"
    }}
  ]
}}

Content to analyze:
{combined_content}
"""
        else:  # summary
            prompt = f"""Analyze the following pages from the CWCki about Chris Chan and create a comprehensive summary.

Focus on:
1. Key biographical information
2. Major life events and their significance
3. Important relationships
4. Notable incidents
5. Chronological progression

Write a well-structured summary that is objective and factual. Use markdown formatting.

Content to analyze:
{combined_content}
"""
        
        try:
            agent_result = self.agent(prompt)
            
            # Extract text content from AgentResult object
            if hasattr(agent_result, 'content'):
                # AgentResult object - extract the content
                response = agent_result.content
            elif hasattr(agent_result, 'text'):
                # Alternative attribute name
                response = agent_result.text
            elif isinstance(agent_result, str):
                # Already a string
                response = agent_result
            else:
                # Try to convert to string
                response = str(agent_result)
            
            return response
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Check if error is retryable
            retryable_errors = [
                'UnrecognizedClientException',  # AWS credential issues
                'ExpiredTokenException',        # Expired AWS credentials - MUST RETRY
                'ThrottlingException',          # Rate limiting
                'ServiceUnavailableException',  # Temporary unavailability
                'InternalServerError',          # Server issues
                'TimeoutError',                 # Timeout
                'ConnectionError'               # Network issues
            ]
            
            is_retryable = any(err in error_type or err in error_msg for err in retryable_errors)
            
            if is_retryable and retry_count < self.max_retries:
                # Exponential backoff
                delay = self.retry_delay * (2 ** retry_count)
                logger.warning(f"AI call failed ({error_type}), retrying in {delay}s (attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(delay)
                return self.analyze_page_batch(pages, purpose, retry_count + 1)
            else:
                logger.error(f"AI call failed permanently: {error_type}: {error_msg}")
                # Raise exception instead of returning empty data
                raise Exception(f"Batch analysis failed after {self.max_retries} retries: {error_type}: {error_msg}")
    
    def generate_timeline(self, output_file: str = "timeline.json"):
        """Generate comprehensive timeline from all pages with checkpoint support"""
        print("\n" + "="*80)
        print("GENERATING TIMELINE")
        print("="*80)
        
        pages = self.load_all_pages()
        checkpoint_file = self.data_dir / "timeline_checkpoint.json"
        
        # Try to load existing checkpoint
        all_events = []
        start_batch = 0
        
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)
                all_events = checkpoint.get('events', [])
                failed_batches = checkpoint.get('failed_batches', [])
                start_batch = checkpoint.get('last_batch', 0)
                
                # If there are failed batches, restart from the first failed one
                if failed_batches:
                    start_batch = min(failed_batches) - 1  # Start from first failed batch
                    logger.info(f"✅ Resumed from checkpoint with {len(failed_batches)} failed batches")
                    logger.info(f"   Events collected: {len(all_events)}")
                    logger.info(f"   Retrying from batch: {start_batch + 1} (first failed)")
                else:
                    logger.info(f"✅ Resumed from checkpoint:")
                    logger.info(f"   Events collected: {len(all_events)}")
                    logger.info(f"   Starting from batch: {start_batch + 1}")
            except Exception as e:
                logger.warning(f"Could not load checkpoint: {e}")
                start_batch = 0
                all_events = []
                failed_batches = []
        else:
            failed_batches = []
        
        # Process in batches - Optimized for maximum content coverage
        batch_size = 5  # 99%+ coverage: ~140K chars per page
        total_batches = (len(pages) + batch_size - 1) // batch_size
        
        print(f"Processing {len(pages)} pages in {total_batches} batches of {batch_size}")
        if failed_batches:
            print(f"Retrying {len(failed_batches)} previously failed batches")
        print("")
        
        # Use progress bar for clean output
        with tqdm(total=total_batches, desc="Analyzing batches", initial=start_batch,
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as pbar:
            
            for i in range(start_batch * batch_size, len(pages), batch_size):
                batch_num = i // batch_size
                batch = pages[i:i+batch_size]
                
                # Update progress bar description
                pbar.set_postfix({'events': len(all_events), 'failed': len(failed_batches)})
                
                try:
                    result = self.analyze_page_batch(batch, purpose="events")
                    
                    # Parse JSON response
                    try:
                        # Extract JSON from markdown code blocks if present
                        json_match = re.search(r'```json\s*(\{.*?\})\s*```', result, re.DOTALL)
                        if json_match:
                            result = json_match.group(1)
                        
                        events_data = json.loads(result)
                        if 'events' in events_data:
                            all_events.extend(events_data['events'])
                            
                            # Remove from failed list if it was there (successful retry)
                            if (batch_num + 1) in failed_batches:
                                failed_batches.remove(batch_num + 1)
                            
                            # Save checkpoint every 5 batches
                            if (batch_num + 1) % 5 == 0:
                                checkpoint_data = {
                                    'events': all_events,
                                    'last_batch': batch_num + 1,
                                    'total_batches': total_batches,
                                    'failed_batches': failed_batches,
                                    'last_updated': datetime.now().isoformat()
                                }
                                with open(checkpoint_file, 'w', encoding='utf-8') as f:
                                    json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
                                
                    except json.JSONDecodeError as e:
                        if (batch_num + 1) not in failed_batches:
                            failed_batches.append(batch_num + 1)
                        # Only log to file, not console
                        logger.info(f"Parse error batch {batch_num + 1}: {str(e)[:50]}")
                        
                except Exception as e:
                    if (batch_num + 1) not in failed_batches:
                        failed_batches.append(batch_num + 1)
                    # Print to console only for critical errors
                    tqdm.write(f"❌ Batch {batch_num + 1} failed: {str(e)[:80]}")
                    # Save checkpoint with failure info (don't increment last_batch on failure)
                    checkpoint_data = {
                        'events': all_events,
                        'last_batch': batch_num,  # Don't increment on failure
                        'total_batches': total_batches,
                        'failed_batches': failed_batches,
                        'last_updated': datetime.now().isoformat()
                    }
                    with open(checkpoint_file, 'w', encoding='utf-8') as f:
                        json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
                
                pbar.update(1)
        
        # Sort events chronologically
        def parse_date_for_sort(date_str):
            try:
                if len(date_str) == 4:  # Just year
                    return (int(date_str), 1, 1)
                elif len(date_str) == 7:  # YYYY-MM
                    parts = date_str.split('-')
                    return (int(parts[0]), int(parts[1]), 1)
                else:  # Full date
                    parts = date_str.split('-')
                    return (int(parts[0]), int(parts[1]), int(parts[2]))
            except:
                return (9999, 1, 1)  # Put unparseable dates at the end
        
        all_events.sort(key=lambda x: parse_date_for_sort(x.get('date', '9999')))
        
        # Report on completion status
        if failed_batches:
            logger.warning(f"\n⚠️  Timeline generation INCOMPLETE!")
            logger.warning(f"   Successfully processed: {total_batches - len(failed_batches)}/{total_batches} batches")
            logger.warning(f"   Failed batches: {len(failed_batches)} - {failed_batches[:10]}{'...' if len(failed_batches) > 10 else ''}")
            logger.warning(f"   Events collected: {len(all_events)}")
            logger.warning(f"\n   Checkpoint preserved at: {checkpoint_file}")
            logger.warning(f"   Run the analyzer again to retry failed batches")
        else:
            logger.info(f"\n✅ Timeline generation COMPLETE!")
            logger.info(f"   All {total_batches} batches processed successfully")
            logger.info(f"   Total events collected: {len(all_events)}")
        
        # Save timeline
        output_path = self.data_dir / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'total_events': len(all_events),
                'generated_at': datetime.now().isoformat(),
                'complete': len(failed_batches) == 0,
                'failed_batches': failed_batches,
                'events': all_events
            }, f, indent=2, ensure_ascii=False)
        
        # Keep checkpoint file (useful for future reference)
        if checkpoint_file.exists():
            logger.info(f"📝 Checkpoint file preserved at: {checkpoint_file}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Timeline generated with {len(all_events)} events")
        logger.info(f"Saved to: {output_path}")
        
        # Also create markdown version
        self.create_timeline_markdown(all_events)
        
        return all_events
    
    def create_timeline_markdown(self, events: List[Dict]):
        """Create markdown formatted timeline"""
        md_path = self.data_dir / "timeline.md"
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("# Chris Chan Timeline\n\n")
            f.write(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
            f.write(f"Total Events: {len(events)}\n\n")
            f.write("---\n\n")
            
            # Group by year
            events_by_year = defaultdict(list)
            for event in events:
                year = event.get('date', '')[:4] if event.get('date') else 'Unknown'
                events_by_year[year].append(event)
            
            for year in sorted(events_by_year.keys()):
                f.write(f"## {year}\n\n")
                
                for event in events_by_year[year]:
                    date = event.get('date', 'Unknown date')
                    desc = event.get('description', 'No description')
                    source = event.get('source', 'Unknown source')
                    category = event.get('category', 'General')
                    
                    f.write(f"### {date}\n")
                    f.write(f"**Category:** {category}  \n")
                    f.write(f"**Event:** {desc}  \n")
                    if event.get('people'):
                        f.write(f"**People:** {', '.join(event['people'])}  \n")
                    f.write(f"**Source:** {source}\n\n")
                
                f.write("\n")
        
        print(f"Markdown timeline saved to: {md_path}")
    
    def generate_summary(self, output_file: str = "summary.md"):
        """Generate comprehensive biographical summary using the timeline as context"""
        print("\n" + "="*80)
        print("GENERATING COMPREHENSIVE SUMMARY")
        print("="*80)
        
        # Check if summary already exists
        summary_path = self.data_dir / output_file
        if summary_path.exists():
            summary_size = summary_path.stat().st_size
            if summary_size > 1000:  # At least 1KB indicates a real summary
                print(f"\n✅ Summary already exists!")
                print(f"   File: {summary_path}")
                print(f"   Size: {summary_size:,} bytes")
                print(f"\n⏭️  Skipping summary generation (already done)")
                print("   To regenerate, delete the existing summary.md file")
                return str(summary_path)
        
        # Load the generated timeline for chronological context
        timeline_path = self.data_dir / "timeline.json"
        if not timeline_path.exists():
            print("⚠️  Warning: timeline.json not found. Generate timeline first.")
            return None
        
        with open(timeline_path, 'r', encoding='utf-8') as f:
            timeline_data = json.load(f)
        
        events = timeline_data.get('events', [])
        
        # Group events by decade for structured analysis
        events_by_decade = defaultdict(list)
        for event in events:
            date = event.get('date', '0000')
            year = date[:4]
            if year.isdigit():
                decade = (int(year) // 10) * 10
                events_by_decade[decade].append(event)
        
        # Generate summary from timeline events (much more accurate)
        print(f"\nAnalyzing {len(events)} events organized by decade...")
        
        prompt = f"""You are analyzing a comprehensive timeline of Chris Chan's life extracted from the CWCki.

Create a detailed biographical summary organized chronologically with the following structure:

1. **Early Life & Background** (1980s-2000)
2. **The Sonichu Creation & Love Quest Era** (2000-2007)
3. **Internet Discovery & Trolling Begins** (2007-2010)
4. **Dark Ages & Personal Struggles** (2011-2015)
5. **Transition & Identity Evolution** (2016-2020)
6. **The Dimensional Merge & Recent Years** (2021-present)

For each period, provide:
- Key developments and turning points
- Important relationships and conflicts
- Major incidents and their impact
- Psychological/behavioral patterns
- How events shaped future developments

Write in an objective, encyclopedic style. Focus on factual documentation while showing how events connect and influence each other over time.

Timeline data ({len(events)} events):

{json.dumps(list(events_by_decade.items())[:20], indent=2)}

[Note: Full timeline has {len(events)} events spanning {min(events_by_decade.keys())} to {max(events_by_decade.keys())}]

Generate a comprehensive, well-structured biographical summary in markdown format.
Do NOT include a title or header at the beginning - start directly with the content."""
        
        try:
            summary_text = self.analyze_page_batch([{'filename': 'timeline', 'content': prompt}], purpose="summary")
            
            # Remove any leading headers from AI response (in case it added one despite instructions)
            lines = summary_text.strip().split('\n')
            while lines and lines[0].startswith('#'):
                lines.pop(0)
                # Also remove empty lines after header
                while lines and not lines[0].strip():
                    lines.pop(0)
            clean_summary = '\n'.join(lines).strip()
            
            final_summary = f"""# Chris Chan: A Comprehensive Biographical Summary

{clean_summary}

---

*Source: [CWCki](https://sonichu.com/cwcki)*
"""
            
            output_path = self.data_dir / output_file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_summary)
            
            print(f"\n{'='*80}")
            print(f"Summary generated from {len(events)} timeline events!")
            print(f"Saved to: {output_path}")
            
            return final_summary
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return None
    
    def generate_worst_things_list(self, output_file: str = "worst_things.md"):
        """Generate list of top 100 worst things committed based on timeline events"""
        print("\n" + "="*80)
        print("GENERATING TOP 100 WORST THINGS COMMITTED LIST")
        print("="*80)
        
        # Check if list already exists
        list_path = self.data_dir / output_file
        if list_path.exists():
            list_size = list_path.stat().st_size
            if list_size > 1000:  # At least 1KB indicates real content
                print(f"\n✅ Worst things committed list already exists!")
                print(f"   File: {list_path}")
                print(f"   Size: {list_size:,} bytes")
                print(f"\n⏭️  Skipping list generation (already done)")
                print("   To regenerate, delete the existing worst_things.md file")
                return str(list_path)
        
        # Load timeline
        timeline_path = self.data_dir / "timeline.json"
        if not timeline_path.exists():
            print("⚠️  Warning: timeline.json not found. Generate timeline first.")
            return None
        
        with open(timeline_path, 'r', encoding='utf-8') as f:
            timeline_data = json.load(f)
        
        events = timeline_data.get('events', [])
        
        # Create analysis prompt
        prompt = f"""YOUR TASK: Create a numbered list of the TOP 100 WORST THINGS COMMITTED in the Chris Chan saga.

DO NOT write a biography. DO NOT write an essay. DO NOT provide historical context.

YOU MUST CREATE A NUMBERED LIST FROM 1 TO 100.

Each entry MUST follow this EXACT format:
**1. Title of Bad Thing (Date)**
Brief description of what happened, who did it, and why it was bad.

**2. Next Bad Thing (Date)**
Brief description.

Continue this pattern through **100. Final Entry (Date)**

REQUIRED CONTENT BALANCE:
- Approximately 33 entries: Things done TO Chris Chan (harassment, manipulation, exploitation by trolls)
- Approximately 33 entries: Things Chris Chan did to others (violence, harassment, criminal acts)
- Approximately 33 entries: Things by others in the saga (parental failures, institutional failures, third-party actions)

EXAMPLES OF WHAT TO INCLUDE:

Things TO Chris:
- Bluespike's psychological torture and blackmail (2009)
- Blanca catfishing operation and medallion destruction (2008)
- Idea Guys manipulation and financial exploitation (2017-2018)
- Mass doxxing and privacy violations by troll groups
- Julie/bluespike forcing Chris to destroy possessions

Things BY Chris:
- Incest with Barbara Chandler (2021)
- Megan Schroeder sexual harassment (2006-2008)
- GameStop pepper spray assault (2014)
- Racist and homophobic behavior throughout life
- Death threats against multiple individuals

Things by OTHERS:
- Bob and Barbara's enabling and neglect of proper treatment
- Educational system failures to provide appropriate support
- Mental health system gaps leaving Chris untreated
- Troll group coordination and organization (Encyclopedia Dramatica, Kiwi Farms)
- Third-party content creators profiting from Chris's suffering

TIMELINE EVENTS TO ANALYZE:
{json.dumps(events[:500], indent=2)}
...and {len(events) - 500} more events

OUTPUT REQUIREMENTS:
- Start immediately with "**1. [Title] (Date)**"
- Number ALL entries from 1 to 100
- NO introductory text
- NO concluding analysis
- JUST the numbered list

BEGIN YOUR NUMBERED LIST NOW:"""
        
        try:
            worst_things_text = self.analyze_page_batch([{'filename': 'timeline', 'content': prompt}], purpose="worst_things_analysis")
            
            # Remove any leading headers from AI response
            lines = worst_things_text.strip().split('\n')
            while lines and lines[0].startswith('#'):
                lines.pop(0)
                while lines and not lines[0].strip():
                    lines.pop(0)
            clean_content = '\n'.join(lines).strip()
            
            final_content = f"""# Top 100 Worst Things Committed in the Chris Chan Saga

{clean_content}

---

*Source: [CWCki](https://sonichu.com/cwcki)*
"""
            
            with open(list_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
            
            print(f"\n{'='*80}")
            print(f"Worst things committed list generated from {len(events)} timeline events!")
            print(f"Saved to: {list_path}")
            
            return str(list_path)
            
        except Exception as e:
            logger.error(f"Failed to generate worst things committed list: {e}")
            return None

    def link_media_to_events(self, output_file: str = "timeline_with_media.json"):
        """Link media to timeline events with checkpoint support"""
        print("\n" + "="*80)
        print("LINKING MEDIA TO TIMELINE EVENTS")
        print("="*80)
        
        # Load timeline
        timeline_path = self.data_dir / "timeline.json"
        if not timeline_path.exists():
            logger.error("Timeline not found. Generate timeline first.")
            return None
        
        with open(timeline_path, 'r', encoding='utf-8') as f:
            timeline_data = json.load(f)
        
        events = timeline_data.get('events', [])
        
        # Load media index
        media_index_path = self.data_dir / "media" / "media_index.json"
        if not media_index_path.exists():
            logger.warning("Media index not found. Skipping media linking.")
            return None
        
        with open(media_index_path, 'r', encoding='utf-8') as f:
            media_data = json.load(f)
        
        # Create page-to-media mapping
        page_media = {}
        for page in media_data.get('pages', []):
            page_media[page['safe_filename']] = {
                'images': page['images'],
                'videos': page['videos']
            }
        
        print(f"\nLinking media to {len(events)} events...")
        print(f"Media available from {len(page_media)} pages\n")
        
        # Checkpoint support
        checkpoint_file = self.data_dir / "media_linking_checkpoint.json"
        start_idx = 0
        events_with_media = []
        
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)
                events_with_media = checkpoint.get('events_with_media', [])
                start_idx = len(events_with_media)
                logger.info(f"✅ Resumed from checkpoint: {start_idx} events linked")
            except Exception as e:
                logger.warning(f"Could not load checkpoint: {e}")
        
        # Link media to events with progress bar
        checkpoint_interval = 100
        events_since_checkpoint = 0
        
        for idx in tqdm(range(start_idx, len(events)), desc="Linking media",
                       initial=start_idx, total=len(events)):
            event = events[idx]
            
            # Get media from source page
            source = event.get('source', '')
            safe_source = re.sub(r'[^\w\s-]', '_', source)[:100]
            
            event_media = {
                'images': [],
                'videos': []
            }
            
            if safe_source in page_media:
                source_media = page_media[safe_source]
                
                # Deduplicate images by URL (same image may appear multiple times on a page)
                seen_urls = set()
                unique_images = []
                for img in source_media.get('images', []):
                    img_url = img.get('url', '')
                    if img_url and img_url not in seen_urls:
                        seen_urls.add(img_url)
                        unique_images.append(img)
                
                # Deduplicate videos by URL
                seen_video_urls = set()
                unique_videos = []
                for video in source_media.get('videos', []):
                    video_url = video.get('url', '')
                    if video_url and video_url not in seen_video_urls:
                        seen_video_urls.add(video_url)
                        unique_videos.append(video)
                
                event_media = {
                    'images': unique_images,
                    'videos': unique_videos
                }
            
            # Add media to event
            events_with_media.append({
                **event,
                'media': event_media
            })
            
            events_since_checkpoint += 1
            
            # Save checkpoint periodically
            if events_since_checkpoint >= checkpoint_interval:
                checkpoint_data = {
                    'events_with_media': events_with_media,
                    'last_updated': datetime.now().isoformat()
                }
                with open(checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
                events_since_checkpoint = 0
        
        # Save final timeline with media
        output_path = self.data_dir / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'total_events': len(events_with_media),
                'events_with_media': sum(1 for e in events_with_media if e['media']['images'] or e['media']['videos']),
                'generated_at': datetime.now().isoformat(),
                'events': events_with_media
            }, f, indent=2, ensure_ascii=False)
        
        # Keep checkpoint as completion marker - allows skipping on reruns
        if checkpoint_file.exists():
            print(f"\n📝 Checkpoint preserved (marks linking as complete)")
        
        print(f"\n✅ Media linking complete!")
        print(f"   Events with media: {sum(1 for e in events_with_media if e['media']['images'] or e['media']['videos'])}")
        print(f"   Saved to: {output_path}")
        
        return events_with_media

def main():
    analyzer = CWCkiAnalyzer()
    
    print("CWCki Content Analyzer")
    print("="*80)
    print("\nThis will analyze all scraped content and generate:")
    print("1. Comprehensive timeline (JSON and Markdown)")
    print("2. Biographical summary (Markdown)")
    print("3. Timeline with media links")
    print("\n" + "="*80)
    
    # Generate timeline
    timeline = analyzer.generate_timeline()
    
    # Link media to events (check if media index has data)
    media_index_path = analyzer.data_dir / "media" / "media_index.json"
    skip_media = False
    
    if media_index_path.exists():
        try:
            with open(media_index_path, 'r') as f:
                media_data = json.load(f)
            if media_data.get('total_pages', 0) == 0:
                print("\n⚠️  Media index is empty, skipping media linking")
                skip_media = True
        except:
            skip_media = True
    else:
        print("\n⚠️  Media index not found, skipping media linking")
        skip_media = True
    
    if not skip_media:
        timeline_with_media = analyzer.link_media_to_events()
    
    # Generate summary
    summary = analyzer.generate_summary()
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)
    print(f"\nFiles generated in: {analyzer.data_dir}")
    print("- timeline.json")
    print("- timeline.md")
    print("- timeline_with_media.json")
    print("- summary.md")

if __name__ == "__main__":
    main()