# 🎨 Chris Chan Interactive Timeline

An interactive, multimedia timeline documenting the life and online presence of Chris Chan, compiled from the comprehensive [CWCki](https://sonichu.com/cwcki).

## 🌐 Live Demo

**View the timeline here:** [https://syamhaque.github.io/CWCki-timeline/](https://syamhaque.github.io/CWCki-timeline/)

## ✨ Features

### 📅 Interactive Timeline Navigation
- **Hierarchical Organization**: Events organized by year and month with collapsible sections
- **Smart Collapse**: Collapse all open months/years and automatically scroll back to last opened section
- **Alternating Layout**: Beautiful zigzag timeline with events alternating left and right

### 🔍 Advanced Filtering & Search
- **Full-text Search**: Search across all event descriptions and associated people
- **Category Filters**: Filter by Personal, Internet, Legal, Business, Politics categories
- **Media Filters**: View only events with images, videos, or any media
- **Smart Sorting**: Sort by newest/oldest year, or by most events per year

### 🖼️ Rich Media Gallery
- **Image Galleries**: View embedded images from CWCki in lightbox viewer
- **Media Indicators**: Visual indicators show which events have associated media
- **Thumbnail Previews**: Quick preview of all media in event cards
- **Toggle Media**: Option to show/hide all media for faster browsing

### 📖 Comprehensive Content
- **Biography Modal**: Full biographical summary with formatted markdown
- **Top 100 List**: Curated list of significant incidents
- **Event Categories**: Color-coded categories for easy visual scanning
- **People Tracking**: Associated individuals listed for each event
- **Date Precision**: Events displayed with appropriate date precision (year, month, or day)

### 🎨 User Experience
- **Responsive Design**: Works seamlessly on desktop, tablet, and mobile
- **Smooth Animations**: Polished transitions and hover effects
- **Keyboard Shortcuts**: Press ESC to close modals and lightboxes
- **Floating Controls**: Quick access to collapse and scroll-to-top functions
- **Visual Timeline**: Continuous timeline with color-coded markers

## 📁 Project Structure

```
CWCki-timeline/
├── index.html                          # Main timeline viewer (GitHub Pages entry point)
├── serve_timeline.sh                   # Local development server script
├── scraped_data/
│   ├── timeline_with_media.json       # Complete timeline with media links
│   ├── timeline.json                  # Timeline data without media
│   ├── summary.md                     # Comprehensive biography
│   ├── worst_things.md                # Top 100 worst things list
│   ├── media/
│   │   ├── images/                    # All timeline images
│   │   └── media_index.json           # Media file index
│   ├── raw_json/                      # Raw scraped data per page
│   └── clean_text/                    # Cleaned text content
└── README.md                           # This file
```

## 🚀 Deployment to GitHub Pages

This repository is configured for GitHub Pages deployment. The timeline is automatically served from the `index.html` file in the root directory.

### Deployment Steps

1. **Push your changes to GitHub:**
   ```bash
   git add .
   git commit -m "Update timeline"
   git push origin main
   ```

2. **Enable GitHub Pages** (if not already enabled):
   - Go to your repository on GitHub
   - Click **Settings** → **Pages**
   - Under "Source", select **Deploy from a branch**
   - Select branch: **main** (or **master**)
   - Select folder: **/ (root)**
   - Click **Save**

3. **Wait for deployment** (usually takes 1-2 minutes)
   - GitHub will build and deploy your site
   - Access your timeline at: `https://syamhaque.github.io/CWCki-timeline/`

### Updating the Timeline

To update the timeline with new data:
1. Run your scraper to generate updated JSON files
2. Commit and push the changes
3. GitHub Pages will automatically rebuild and redeploy

## 💻 Local Development

To run the timeline locally for testing:

### Option 1: Using the included script
```bash
chmod +x serve_timeline.sh
./serve_timeline.sh
```

### Option 2: Using Python
```bash
python3 -m http.server 8000
# Open http://localhost:8000/index.html in your browser
```

### Option 3: Using Node.js
```bash
npx http-server -p 8000
# Open http://localhost:8000/index.html in your browser
```

## 📊 Data Sources

All data is sourced from the [CWCki](https://sonichu.com/cwcki), a comprehensive wiki documenting Chris Chan's life and online activities. The timeline includes:

- **1,000+ events** spanning multiple decades
- **Categories**: Personal, Internet, Legal, Business, Politics
- **Media**: Images, videos, and documents from CWCki
- **People**: Associated individuals for each event
- **Precision**: Events dated by year, month, or specific day

## 🔧 Technical Details

### Technologies Used
- **HTML5/CSS3**: Modern, semantic markup and styling
- **Vanilla JavaScript**: No frameworks, optimized for performance
- **Markdown**: Content formatting for biography and lists
- **JSON**: Structured data storage
- **Git/GitHub**: Version control and hosting

### Browser Compatibility
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

### Performance
- Lazy loading of large datasets
- Efficient DOM manipulation
- Optimized image loading with fallbacks
- Smooth scrolling and animations

## 📝 Credits

- **Data Source**: [CWCki](https://sonichu.com/cwcki) - Comprehensive Chris Chan documentation
- **Developer**: Syam Haque
- **Repository**: [github.com/syamhaque/CWCki-timeline](https://github.com/syamhaque/CWCki-timeline)

## 📄 License

This project compiles publicly available information from the CWCki. All original content and media are credited to their respective sources.

---

**Note**: This is a documentary timeline for educational and archival purposes. All information is sourced from publicly available materials on the CWCki.