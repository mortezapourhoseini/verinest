# Contributing to VeriNest

Thanks for helping! VeriNest is deliberately simple: a Python standard-library backend and a
vanilla-JS front-end with no build step. You can hack on it with just a text editor.

## Run from source

```bash
sudo apt install iverilog verilator     # verilator optional
python3 -m verinest                     # opens the app window
python3 -m verinest --serve --port 8765 # server only, then open the printed URL in a browser
python3 -m verinest --selftest          # simulate all examples
python3 -m unittest discover tests      # backend unit tests (no simulator needed)
```

Edit files in `web/` and simply reload the page (<kbd>Ctrl</kbd>+<kbd>R</kbd>). Restart
the server after changing Python files. Set `VERINEST_HOME=/tmp/vn` to use a throw-away
workspace, and `VERINEST_DEBUG=1` to log HTTP requests.

## Good first contributions

* **A new example**: add `examples/NN_name/` with the design files, a self-checking
  testbench that prints `PASS` or `FAIL`, and an `example.json`:
  ```json
  {"title": "...", "level": "basic|intermediate|advanced", "project": "folder_name",
   "description": "...", "top": "tb_name", "open": "file_to_open_first.v"}
  ```
  Run `python3 -m verinest --selftest` before opening a PR.
* **Better error explanations**: `verinest/explain.py` (`RULES` for Icarus messages,
  `VERILATOR_CODES` for Verilator warnings). Please add the raw message you saw to the PR.
* **Suggestion rules**: `web/suggest.js`. A suggestion is one string; `\u0001` marks where
  the cursor goes after the user accepts it.
* **Formatter cases**: `verinest/formatter.py`. It must only change whitespace and must
  be idempotent (formatting twice gives the same result).

## Guidelines

* Keep the backend dependency-free (Python standard library only).
* Keep the front-end free of build tools and CDNs: VeriNest must work offline.
* UI text and error explanations are in English; translations are welcome as separate files.
* Examples are Verilog-2005 and must pass with Icarus Verilog 11+.
* One topic per pull request. Include a screenshot for UI changes.

## Reporting bugs

Please include your distribution, `iverilog -V`, `verilator --version`, the output of
`verinest --selftest`, and the smallest Verilog code that shows the problem.
