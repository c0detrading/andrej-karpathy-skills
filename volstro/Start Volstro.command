#!/bin/bash
# Double-click on macOS to start the Volstro pipeline and open it in the browser.
cd "$(dirname "$0")"
# Already running? Just open it.
if curl -s -o /dev/null http://localhost:8100/login; then open http://localhost:8100; exit 0; fi
echo "Installing/updating requirements..."
python3 -m pip install -q -r requirements.txt
echo "Starting Volstro - keep this window open. Close it to stop."
(sleep 5; open http://localhost:8100) &
python3 -m pipeline
