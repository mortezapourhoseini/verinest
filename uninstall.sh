#!/usr/bin/env bash
# Removes VeriNest. Your projects in ~/VeriNest are NOT deleted.
rm -rf "$HOME/.local/share/verinest" "$HOME/.local/bin/verinest" "$HOME/.local/share/applications/verinest.desktop" \
       "$HOME/.config/verinest"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" 2>/dev/null
echo "VeriNest removed. Your projects are still in ~/VeriNest."
echo "(iverilog and verilator were left installed: sudo apt remove iverilog verilator)"
