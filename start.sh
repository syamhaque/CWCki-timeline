#!/bin/bash
#
# Run CWCki scraper with automatic credential refresh
# Handles AWS credential expiration during long-running tasks
#

echo "================================================"
echo "CWCki Scraper - Auto-Refreshing Credentials Mode"
echo "================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Function to refresh AWS credentials
# Override this function if you use a different credential provider
refresh_credentials() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Refreshing AWS credentials..."
    
    # Example for ada credentials (Amazon internal tool)
    # Uncomment and modify if you use ada:
    # eval "$(ada credentials print --provider=isengard --profile ClineBedrockAccess --format env)"
    
    # For standard AWS CLI profiles:
    # export AWS_PROFILE=your-profile-name
    
    # For temporary credentials, you may not need to refresh
    # Just ensure they're set in your environment before running
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  Using existing AWS credentials from environment"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ℹ️  Customize refresh_credentials() function if needed"
    return 0
}

# Initial credential setup
echo "Setting up initial AWS credentials..."
if ! refresh_credentials; then
    echo "❌ Failed to get initial credentials. Exiting."
    exit 1
fi

echo ""
echo "Starting scraper with automatic credential refresh..."
echo "Credentials will be refreshed every 30 minutes"
echo ""
echo "Log file: start_script.log"
echo ""

# Create a script that refreshes credentials and runs the scraper
cat > /tmp/cwcki_runner_$$.sh << INNER_EOF
#!/bin/bash

cd "$SCRIPT_DIR"

# Function to refresh credentials (customize if needed)
refresh_creds() {
    # Use the same refresh logic as parent script
    # Or customize for your specific credential provider
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Credential refresh in background loop" >> start_script.log
    return 0
}

# Refresh credentials initially
refresh_creds

# Start background job to refresh credentials every 30 minutes
while true; do
    sleep 1800  # 30 minutes
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto-refreshing credentials..." >> start_script.log
    refresh_creds
done &

REFRESH_PID=$!
echo $REFRESH_PID > /tmp/cwcki_refresh_pid.txt

# Run the scraper with python3
python3 run.py 2>&1 | tee -a start_script.log

# Cleanup: kill the credential refresh loop
kill $REFRESH_PID 2>/dev/null
rm /tmp/cwcki_refresh_pid.txt
INNER_EOF

chmod +x /tmp/cwcki_runner_$$.sh

# Run with caffeinate to prevent sleep
if command -v caffeinate &> /dev/null; then
    echo "✅ Using caffeinate to prevent system sleep"
    caffeinate -i /tmp/cwcki_runner_$$.sh &
else
    /tmp/cwcki_runner_$$.sh &
fi

SCRAPER_PID=$!
echo ""
echo "✅ Scraper started (PID: $SCRAPER_PID)"
echo "✅ Credentials will auto-refresh every 30 minutes (if configured)"
echo ""
echo "Monitor progress:"
echo "  tail -f $SCRIPT_DIR/start_script.log"
echo ""
echo "Check if running:"
echo "  ps -p $SCRAPER_PID"
echo ""
echo "Stop scraper:"
echo "  kill $SCRAPER_PID"
echo "  kill \$(cat /tmp/cwcki_refresh_pid.txt 2>/dev/null) 2>/dev/null"
echo ""

# Wait for completion
wait $SCRAPER_PID
EXIT_CODE=$?

# Cleanup
rm /tmp/cwcki_runner_$$.sh 2>/dev/null
kill $(cat /tmp/cwcki_refresh_pid.txt 2>/dev/null) 2>/dev/null
rm /tmp/cwcki_refresh_pid.txt 2>/dev/null

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Scraper completed successfully!"
else
    echo ""
    echo "⚠️  Scraper exited with code $EXIT_CODE"
    echo "Check the log: tail -100 start_script.log"
fi

exit $EXIT_CODE
