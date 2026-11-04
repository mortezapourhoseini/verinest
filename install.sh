#!/usr/bin/env bash
# VeriNest installer for Linux Mint / Ubuntu / Debian
#   ./install.sh            install (asks for sudo only to install packages)
#   ./install.sh --no-apt   skip package installation
set -e

APP_NAME="VeriNest"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.local/share/verinest"
BIN="$HOME/.local/bin"
DESKTOP="$HOME/.local/share/applications/verinest.desktop"

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
ok()   { printf "  \033[32m✔\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }

bold "Installing $APP_NAME"

# ---------------------------------------------------------------- packages
# 1) try apt normally; 2) if that fails (e.g. HTTP mirrors blocked), download the
#    .deb over HTTPS, verify its SHA256 against apt's own package list, install it.
install_pkg() {
    local pkg="$1"
    command -v "$2" >/dev/null 2>&1 && return 0
    bold "Installing $pkg"
    if sudo apt-get install -y --no-upgrade "$pkg" >/tmp/verinest-apt.log 2>&1; then
        ok "$pkg installed with apt"; return 0
    fi
    warn "apt could not download $pkg, trying HTTPS mirrors..."
    local debs=""
    # ask apt which files it needs (the package + missing dependencies) and their hashes
    sudo apt-get install --print-uris -qq -y --no-upgrade "$pkg" > /tmp/verinest-uris.txt 2>/dev/null || true
    if grep -q "^'" /tmp/verinest-uris.txt 2>/dev/null; then
        debs=$(python3 "$SRC/tools/fetch_deb.py" --uris /tmp/verinest-uris.txt) || debs=""
    fi
    [ -z "$debs" ] && { debs=$(python3 "$SRC/tools/fetch_deb.py" "$pkg") || return 1; }
    # shellcheck disable=SC2086
    if sudo dpkg -i $debs; then
        ok "$pkg installed"; return 0
    fi
    warn "$pkg needs other packages that are missing; removing the half-installed package"
    sudo dpkg -r "$pkg" >/dev/null 2>&1 || true
    return 1
}

if [ "$1" != "--no-apt" ] && command -v dpkg >/dev/null 2>&1; then
    command -v python3 >/dev/null 2>&1 || { echo "python3 is required: sudo apt install python3"; exit 1; }
    if ! command -v iverilog >/dev/null 2>&1 || ! command -v verilator >/dev/null 2>&1; then
        sudo -v || true
    fi
    install_pkg iverilog iverilog || warn "Icarus Verilog could not be installed automatically (see README: manual install)"
    install_pkg verilator verilator || warn "Verilator could not be installed (optional: only adds extra warnings)"
fi

command -v iverilog >/dev/null 2>&1 && ok "Icarus Verilog: $(iverilog -V 2>&1 | head -n1)" || warn "Icarus Verilog not found (simulation will not work)"
command -v verilator >/dev/null 2>&1 && ok "Verilator: $(verilator --version 2>&1 | head -n1)" || warn "Verilator not found (optional)"

# ---------------------------------------------------------------- files
rm -rf "$DEST"
mkdir -p "$DEST" "$BIN" "$(dirname "$DESKTOP")"
cp -r "$SRC/verinest" "$SRC/web" "$SRC/examples" "$SRC/tools" "$DEST/"
cp "$SRC/README.md" "$SRC/uninstall.sh" "$DEST/" 2>/dev/null || true
find "$DEST" -name "__pycache__" -type d -prune -exec rm -rf {} +
ok "Files copied to $DEST"

cat > "$BIN/verinest" <<EOF
#!/usr/bin/env bash
cd "$DEST" && exec python3 -m verinest "\$@"
EOF
chmod +x "$BIN/verinest"
ok "Command installed: $BIN/verinest"

cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=VeriNest
GenericName=Verilog IDE
Comment=Write, check and simulate Verilog and view waveforms
Exec=$BIN/verinest
Icon=$DEST/web/icon.svg
Terminal=false
Categories=Development;Electronics;Education;IDE;
Keywords=verilog;hdl;fpga;simulation;waveform;iverilog;
StartupWMClass=VeriNest
EOF
chmod +x "$DESKTOP"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
ok "Menu entry created (Menu → Programming → VeriNest)"

# window back-end
if command -v google-chrome >/dev/null 2>&1 || command -v chromium >/dev/null 2>&1 || command -v chromium-browser >/dev/null 2>&1 || command -v brave-browser >/dev/null 2>&1; then
    ok "Window: Chrome/Chromium app mode"
elif python3 -c "import webview" 2>/dev/null; then
    ok "Window: pywebview"
else
    warn "No Chrome/Chromium found: VeriNest will open in your default browser."
fi

echo
bold "Done!  Start VeriNest from the menu (Programming → VeriNest)."
case ":$PATH:" in
    *":$BIN:"*)
        echo "Check that everything works:   verinest --selftest";;
    *)
        echo "Check that everything works:   ~/.local/bin/verinest --selftest"
        echo "(the short command 'verinest' works after you log out and in again)";;
esac
