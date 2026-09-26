#!/bin/bash
# Double-click on macOS to start the station and open it in the browser.
cd "$(dirname "$0")"
echo "Installing/updating requirements..."
python3 -m pip install -q -r requirements.txt
echo "Starting ONYX - keep this window open. Close it to stop."
(sleep 5; open http://localhost:8000) &
python3 -m uvicorn station.app:app --port 8000
