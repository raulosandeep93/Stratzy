#!/bin/bash
echo "╔══════════════════════════════════════════╗"
echo "║   Stratzy Algo Scanner - Starting...     ║"
echo "╚══════════════════════════════════════════╝"

# Kill any existing server on port 5050
fuser -k 5050/tcp 2>/dev/null

# Install dependencies if needed
pip install flask flask-cors requests openpyxl xlrd pandas -q

# Start server
cd "$(dirname "$0")"
python3 server.py &
SERVER_PID=$!

sleep 2

echo ""
echo "✅ Server started! Opening browser..."
echo "   URL: http://localhost:5050"
echo ""
echo "   To stop: kill $SERVER_PID  or  Ctrl+C"
echo ""

# Open browser
xdg-open http://localhost:5050 2>/dev/null || \
  google-chrome http://localhost:5050 2>/dev/null || \
  chromium-browser http://localhost:5050 2>/dev/null || \
  echo "Please open http://localhost:5050 in your browser"

wait $SERVER_PID
