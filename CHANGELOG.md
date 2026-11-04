# Changelog

## 1.1.0 (2026-11-04)
- **Auto Save**: files are saved 1 s after you stop typing (toggle in the status bar)
- Waveform: testbench outputs such as `y` are shown by default (Icarus can split one scope into
  several VCD blocks; these are now merged)
- Console: short file names instead of the internal build path in simulator messages

## 1.0.3 (2026-11-04), first public release
- Desktop window (Chrome/Chromium app mode, pywebview or browser fallback)
- Monaco editor with one-at-a-time inline suggestions (Tab / Enter to accept)
- Live error checking with Icarus Verilog, Verilator and structure checks, with plain-English explanations
- Clean Code formatter, testbench generator, F5 simulation, built-in waveform viewer
- Nine example projects with self-checking testbenches, verified with `--selftest` on Linux Mint 22
- Installer with HTTPS fallback (verified `.deb` downloads) for networks that block plain-HTTP mirrors
