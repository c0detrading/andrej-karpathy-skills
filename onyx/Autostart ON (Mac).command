#!/bin/bash
# Starts ONYX in the background now and every time you log in to your Mac.
cd "$(dirname "$0")"
DIR="$(pwd)"
PY="$(command -v python3)"
case "$DIR" in
  "$HOME/Documents"*|"$HOME/Desktop"*|"$HOME/Downloads"*)
    echo "Note: macOS blocks background apps from reading Documents, Desktop and Downloads."
    echo "If ONYX doesn't start, move the ONYX folder to your home folder ($HOME) and run this again." ;;
esac
echo "Installing/updating requirements..."
"$PY" -m pip install -q -r requirements.txt
mkdir -p "$HOME/Library/LaunchAgents" data
PLIST="$HOME/Library/LaunchAgents/com.onyx.station.plist"
xml() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.onyx.station</string>
  <key>ProgramArguments</key><array><string>$(xml "$PY")</string><string>-m</string><string>station</string></array>
  <key>WorkingDirectory</key><string>$(xml "$DIR")</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>StandardOutPath</key><string>$(xml "$DIR")/data/onyx.log</string>
  <key>StandardErrorPath</key><string>$(xml "$DIR")/data/onyx.log</string>
</dict></plist>
PLIST
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"
echo "ONYX now runs in the background and starts automatically when you log in."
echo "Open it any time at http://localhost:8000. Log file: $DIR/data/onyx.log"
sleep 6
open http://localhost:8000
