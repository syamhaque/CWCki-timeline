# Media-Enhanced Timeline System

This document explains the media scraping and linking features added to the CWCki scraper.

## Overview

The system now:
1. **Scrapes all images** from wiki pages (with size limits)
2. **Extracts video URLs** (YouTube embeds, etc.)
3. **Links media to timeline events** based on source pages
4. **Displays visual timeline** with inline photos and videos

## How It Works

### Phase 1: Media Scraping (scraper.py)

During page scraping, the system:
- Extracts all `<img>` tags from page content
- Downloads images to `scraped_data/media/images/`
- Skips images >10MB (configurable)
- Captures image metadata (alt text, captions, titles)
- Extracts video embeds (YouTube iframes, video tags)
- Creates `media_index.json` linking media to source pages

**Media Storage Structure**:
```
scraped_data/
├── media/
│   ├── images/
│   │   ├── Page_Name_0_abc123.jpg
│   │   ├── Page_Name_1_def456.png
│   │   └── ...
│   └── media_index.json
```

### Phase 2: Media-Event Linking (analyzer.py)

After timeline generation:
- Reads `timeline.json` events
- Reads `media_index.json`
- Links events to media from their source page
- Generates `timeline_with_media.json`

**Logic**: Events have a `source` field (wiki page name). Media from that same page gets attached to the event.

### Phase 3: Visual Timeline Viewer (timeline_viewer_media.html)

Enhanced HTML viewer with:
- **Image Galleries**: Inline thumbnails for each event
- **Video Embeds**: YouTube videos play inline
- **Lightbox Modal**: Click images for full-size view
- **Media Filters**: Filter events by media type
- **Responsive Design**: Works on mobile and desktop
- **Stats Dashboard**: Shows total images/videos count

## Usage

### For Already-Scraped Pages (Your Situation)

Since pages are already scraped, extract media separately:

```bash
# Step 1: Extract media from scraped pages
python extract_media.py

# Step 2: Generate/complete timeline (if not done)
python analyzer.py

# Step 3: View visual timeline
./serve_timeline.sh
```

Then open: http://localhost:8000/timeline_viewer_media.html

### For Fresh Scraping (Future Runs)

If starting fresh, run:
```bash
./start.sh
```

This will scrape pages WITH media extraction built-in.

**Note**: Since your pages are already scraped, use the "Already-Scraped" workflow above.

### View Visual Timeline

```bash
./serve_timeline.sh
```

Then open: http://localhost:8000/timeline_viewer_media.html

### Media Statistics

After scraping completes, check:
```bash
cat scraped_data/media/media_index.json | jq '.total_images, .total_videos'
```

## Configuration

### Image Size Limit

In `scraper.py`, adjust:
```python
self.max_image_size = 10 * 1024 * 1024  # 10MB max
```

### Batch Sizes

In `analyzer.py`, adjust for your needs:
```python
batch_size = 5  # 5 pages per batch = 140K chars/page
```

## Output Files

| File | Description |
|------|-------------|
| `scraped_data/media/images/` | Downloaded images |
| `scraped_data/media/media_index.json` | Complete media catalog |
| `scraped_data/timeline_with_media.json` | Timeline with media links |
| `timeline_viewer_media.html` | Visual timeline viewer |

## Expected Results

For a wiki with ~2,800 pages:
- **Images**: 500-2,000 downloaded (varies by wiki)
- **Videos**: 50-200 video URLs
- **Storage**: 500MB-2GB (depends on image count)
- **Additional Time**: +1-2 hours for media download
- **Additional Cost**: Minimal (no extra AI calls for basic linking)

## Features

### Image Gallery
- Displays all images from source page
- Thumbnails in grid layout
- Click to view full-size in lightbox
- Captions from wiki when available

### Video Embeds
- YouTube videos embedded inline
- Play directly in timeline
- Responsive embed sizing

### Filters
- **Search**: Find events by keywords
- **Category**: Filter by event type
- **Media**: Show only events with images/videos
- **Date Range**: (Coming soon)

## Troubleshooting

### Images not loading
- Check `scraped_data/media/images/` directory exists
- Verify images downloaded (check media_index.json)
- Check browser console for path errors

### Large download
- Some wikis have many images
- Adjust `max_image_size` to skip large files
- Check disk space before running

### Missing media links
- Ensure scraping completed with media extraction
- Check `media_index.json` was created
- Re-run analyzer if timeline was generated before media scraping

## Next Steps

1. Run `./start.sh` to scrape with media
2. Wait for completion (~5-8 hours with media)
3. Open `timeline_viewer_pro.html` to view results (supports both timeline and media)
4. Enjoy your visual timeline with photos and videos!

## Viewing the Timeline

```bash
./serve_timeline.sh
```

This will automatically open the best available viewer (timeline_viewer_pro.html) in your browser.