#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"
PORT=8765

# If port 8765 is in use, find next free port
while lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; do
    PORT=$((PORT+1))
done

echo "=========================================================="
echo " 🚀 Starting LinkedIn AI Job Suite & Application Tracker"
echo " 🌐 Web URL: http://localhost:$PORT/"
echo " 📁 Or open directly: file://$DIR/job_gui.html"
echo "=========================================================="

# Open browser if desktop utility is available
if command -v xdg-open > /dev/null 2>&1; then
    xdg-open "http://localhost:$PORT/" >/dev/null 2>&1 &
fi

python3 "$DIR/server.py" $PORT
