#!/bin/bash
# Builds "/Applications/Claude Usage.app" (menu bar only, no Dock icon) and
# a login item so it starts automatically. Re-run if this folder moves.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="/Applications/Claude Usage.app"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { uv venv -q --python 3.11 "$ROOT/.venv"; uv pip install -q --python "$PY" pyobjc-framework-Cocoa; }

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cat > "$APP/Contents/MacOS/ClaudeUsage" <<SH
#!/bin/bash
exec "$PY" "$ROOT/usage_bar.py" >> "$HOME/Library/Logs/ClaudeUsage.log" 2>&1
SH
chmod +x "$APP/Contents/MacOS/ClaudeUsage"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Claude Usage</string>
  <key>CFBundleIdentifier</key><string>local.claude-usage-bar</string>
  <key>CFBundleExecutable</key><string>ClaudeUsage</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>NSHumanReadableCopyright</key><string>© 2026 Afif Tabish</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
PLIST
touch "$APP"

# Start at login, and restart automatically if it crashes (not after Quit)
AGENT="$HOME/Library/LaunchAgents/local.claude-usage-bar.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$AGENT" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>local.claude-usage-bar</string>
  <key>ProgramArguments</key><array><string>$APP/Contents/MacOS/ClaudeUsage</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ProcessType</key><string>Interactive</string>
</dict>
</plist>
PLIST
echo "Built $APP"
echo "Login item: $AGENT"
