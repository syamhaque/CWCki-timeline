# How to Run - Complete Instructions

## 🎯 Recommended Method (Best for Long Runs)

Use this script for maximum reliability - it handles sleep prevention AND credential refresh:

```bash
./start.sh
```

**This handles everything automatically:**
- ✅ Prevents Mac from sleeping (on macOS with caffeinate)
- ✅ Auto-refreshes AWS credentials every 30 minutes
- ✅ Runs in background
- ✅ Saves output to `start_script.log`
- ✅ Survives terminal closure

## 📊 Monitor Progress

```bash
# Watch live
tail -f start_script.log

# Check status
ps aux | grep run.py

# Count pages scraped
ls scraped_data/clean_text/ 2>/dev/null | wc -l
```

## ⏱️ Expected Runtime

```
Phase 1: Discovery    → 3 hours  (finding 2,843 pages)
Phase 2: Scraping     → 2 hours  (downloading content)
Phase 3: AI Analysis  → 2-3 hours (generating outputs)
────────────────────────────────────────────────────
Total:                  7-8 hours
```

## 📁 Output Location

All results will be in: `./scraped_data/`

```
scraped_data/
├── raw_json/           # JSON files with page metadata
├── clean_text/         # Clean text files
├── media/              # Downloaded images and videos
├── timeline.json       # Structured timeline
├── timeline.md         # Human-readable timeline
├── summary.md          # Comprehensive biography
└── worst_things.md     # Top 100 worst things list
```

## 🛑 How to Stop

```bash
# Find process ID
ps aux | grep run.py

# Stop it
kill <PID>

# Also kill credential refresher
kill $(cat /tmp/cwcki_refresh_pid.txt 2>/dev/null)
```

## ⚠️ Important Notes

1. **Keep laptop plugged in** - 7-8 hours of runtime
2. **Don't close terminal** - Until you see "Scraper started" message
3. **Credentials auto-refresh** - Every 30 minutes
4. **Check progress occasionally** - Via tail command above

## 🔧 Alternative Methods

### Method 2: Foreground (Interactive)
```bash
# Set AWS credentials (adjust based on your setup)
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_SESSION_TOKEN=your_token  # if using temporary credentials

# Run with sleep prevention (macOS)
caffeinate -i python3 run.py

# Or run directly
python3 run.py
```
Keep terminal open, see real-time output.

## ✅ After Completion

```bash
# View results
open scraped_data/

# Read timeline
open scraped_data/timeline.md

# Read biography
open scraped_data/summary.md

# Read worst things list
open scraped_data/worst_things.md

# Check statistics
cat scraped_data/scrape_summary.json
```

## 🐛 Troubleshooting

**Scraper stopped?**
```bash
tail -100 start_script.log
```

**Credentials expired?**
- Refresh your AWS credentials based on your authentication method
- If using temporary credentials, they typically expire after 1 hour
- The start.sh script auto-refreshes credentials every 30 minutes

**Mac went to sleep?**
- System Settings → Energy → Prevent automatic sleeping when plugged in
- Or use the `caffeinate` command (included in start.sh)

**Want to resume?**
- Just run the script again - it automatically skips already-scraped pages
- Checkpoints are saved every 50 pages

---

## 🚀 Ready to Start?

**Single command to run everything:**

```bash
./start.sh
```

Then monitor with:
```bash
tail -f start_script.log
```

**That's it!** Let it run and check back in 7-8 hours for your complete CWCki analysis.
