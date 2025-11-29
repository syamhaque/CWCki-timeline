#!/bin/bash
# Simple local server for timeline viewer

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check which viewer to use (prefer pro version)
if [ -f "scraped_data/timeline_with_media.json" ]; then
    VIEWER="timeline_viewer_pro.html"
    echo "📸 Opening Pro Timeline (with media & hierarchical navigation)..."
elif [ -f "scraped_data/timeline.json" ]; then
    VIEWER="timeline_viewer_pro.html"
    echo "📄 Opening Pro Timeline (hierarchical navigation)..."
else
    echo "❌ No timeline found. Run the scraper first."
    exit 1
fi

echo "🌐 Starting server..."
echo "Opening: http://localhost:8000/$VIEWER"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Setup trap to kill server on Ctrl+C
cleanup() {
    echo ""
    echo "🛑 Stopping server..."
    kill $SERVER_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start server in background with suppressed logs
python3 -m http.server 8000 >/dev/null 2>&1 &
SERVER_PID=$!

# Wait then open browser
sleep 2
open "http://localhost:8000/$VIEWER" 2>/dev/null || \
    echo "Please open http://localhost:8000/$VIEWER in your browser"

# Wait for server (trap will handle Ctrl+C)
wait $SERVER_PID

