#!/bin/bash
# Stops the background ONYX and removes it from login items.
PLIST="$HOME/Library/LaunchAgents/com.onyx.station.plist"
launchctl unload "$PLIST" 2>/dev/null
rm -f "$PLIST"
curl -s -o /dev/null -X POST -H "Content-Type: application/json" -d "{}" http://localhost:8000/api/shutdown
echo "ONYX autostart removed and the background server stopped."
