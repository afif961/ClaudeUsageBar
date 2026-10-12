#!/bin/bash
# Builds a shareable "dist/Claude-Usage-<version>-<arch>.dmg": a self-contained
# Claude Usage.app (no Python needed on the other Mac), a shortcut to
# Applications to drag it onto, and "How to install.txt".
# The app is built for the arch of this Mac (Intel or Apple Silicon).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"

VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"$/\1/p' usage_bar.py)"
[ -n "$VERSION" ] || { echo "APP_VERSION not found in usage_bar.py" >&2; exit 1; }
case "$(uname -m)" in arm64) ARCH=apple-silicon ;; *) ARCH=intel ;; esac
DMG="dist/Claude-Usage-$VERSION-$ARCH.dmg"

if [ ! -x "$PY" ]; then
  if command -v uv >/dev/null; then uv venv -q --python 3.11 .venv
  else python3 -m venv .venv; fi
fi
if command -v uv >/dev/null; then uv pip install -q --python "$PY" -r requirements.txt
else "$PY" -m pip install -q -r requirements.txt; fi

rm -rf build "dist/Claude Usage" "dist/Claude Usage.app"
"$PY" -m PyInstaller --noconfirm --log-level WARN "Claude Usage.spec"

# Ad-hoc signature, so Apple Silicon Macs will launch it (not a Developer ID)
codesign --force --deep --sign - "dist/Claude Usage.app"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "dist/Claude Usage.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp "packaging/How to install.txt" "$STAGE/"
rm -f "$DMG"
hdiutil create -quiet -volname "Claude Usage" -srcfolder "$STAGE" -fs HFS+ -format UDZO "$DMG"
echo "Built $DMG ($(du -h "$DMG" | cut -f1))"
