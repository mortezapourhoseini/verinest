#!/usr/bin/env bash
# VeriNest installer for macOS (from source, uses Homebrew).
# Most users should rather download the .dmg from the GitHub Releases page.
set -e

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/Library/Application Support/VeriNest/app"
APP="$HOME/Applications/VeriNest.app"
BIN="$HOME/.local/bin"

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
ok()   { printf "  \033[32m✔\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }

bold "Installing VeriNest (macOS)"

if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required: https://brew.sh  (or download the VeriNest .dmg instead)"
    exit 1
fi

command -v iverilog >/dev/null 2>&1 || brew install icarus-verilog
ok "Icarus Verilog: $(iverilog -V 2>&1 | head -n1)"
if [ "$1" = "--with-verilator" ]; then
    command -v verilator >/dev/null 2>&1 || brew install verilator || warn "verilator not installed (optional)"
fi

PY="$(command -v python3 || true)"
if [ -z "$PY" ] || ! "$PY" -c "import sys; assert sys.version_info >= (3, 8)" 2>/dev/null; then
    brew install python
    PY="$(brew --prefix)/bin/python3"
fi
ok "Python: $("$PY" --version)"

# native window (optional): pywebview uses the WebKit engine built into macOS
if "$PY" -c "import webview" 2>/dev/null; then
    ok "pywebview already installed"
elif "$PY" -m pip install --user --quiet pywebview 2>/dev/null || \
     "$PY" -m pip install --user --quiet --break-system-packages pywebview 2>/dev/null; then
    ok "pywebview installed (native window)"
else
    warn "pywebview not installed: VeriNest will open in Chrome app mode or your browser"
fi

rm -rf "$DEST"
mkdir -p "$DEST" "$BIN"
cp -R "$SRC/verinest" "$SRC/web" "$SRC/examples" "$DEST/"
find "$DEST" -name "__pycache__" -type d -prune -exec rm -rf {} +
ok "Files copied to $DEST"

# a small .app wrapper so VeriNest appears in Launchpad / Spotlight
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$SRC/packaging/macos/verinest.icns" "$APP/Contents/Resources/"
cat > "$APP/Contents/MacOS/VeriNest" <<EOF
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"
cd "$DEST" && exec "$PY" -m verinest "\$@"
EOF
chmod +x "$APP/Contents/MacOS/VeriNest"
cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>VeriNest</string>
  <key>CFBundleDisplayName</key><string>VeriNest</string>
  <key>CFBundleIdentifier</key><string>io.github.mortezapourhoseini.verinest.local</string>
  <key>CFBundleExecutable</key><string>VeriNest</string>
  <key>CFBundleIconFile</key><string>verinest.icns</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
EOF
ok "App created: $APP (Launchpad / Spotlight: VeriNest)"

cat > "$BIN/verinest" <<EOF
#!/bin/bash
cd "$DEST" && exec "$PY" -m verinest "\$@"
EOF
chmod +x "$BIN/verinest"
ok "Command: $BIN/verinest"

echo
bold "Done!  Open VeriNest from Launchpad, or run:  $BIN/verinest --selftest"
