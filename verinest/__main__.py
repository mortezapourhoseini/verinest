"""VeriNest launcher.

  verinest              open the app in its own window
  verinest --browser    open in the default web browser instead
  verinest --selftest   simulate every bundled example and report PASS/FAIL
  verinest --serve      only run the server (prints the URL)
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

from . import server, core, __version__

APP_BROWSERS = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'brave-browser',
                'microsoft-edge', 'vivaldi']


def _url(srv):
    return 'http://127.0.0.1:%d/?t=%s' % (srv.server_address[1], server.TOKEN)


def _wait_idle(timeout=45):
    """Used when the UI runs in a normal browser tab: exit when the tab stops pinging."""
    server.LAST_PING[0] = time.time() + 30
    while True:
        time.sleep(3)
        if time.time() - server.LAST_PING[0] > timeout:
            return


def run_window(srv, force_browser=False):
    url = _url(srv)
    if not force_browser:
        # 1) Chrome/Chromium "app mode": a standalone window, no tabs or address bar
        for b in APP_BROWSERS:
            exe = shutil.which(b)
            if not exe:
                continue
            profile = os.path.expanduser('~/.config/verinest/window')
            os.makedirs(profile, exist_ok=True)
            p = subprocess.Popen([exe, '--app=' + url, '--user-data-dir=' + profile, '--class=VeriNest',
                                  '--name=VeriNest', '--window-size=1440,900', '--no-first-run',
                                  '--no-default-browser-check', '--disable-features=Translate'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            t0 = time.time()
            p.wait()
            if time.time() - t0 < 5:
                # the window was handed to an already-running VeriNest browser process:
                # keep serving while the window keeps pinging us
                _wait_idle()
            return
        # 2) pywebview (GTK WebKit) if installed
        try:
            import webview  # type: ignore
            webview.create_window('VeriNest', url, width=1440, height=900, min_size=(900, 600))
            webview.start()
            return
        except Exception:
            pass
    # 3) default browser tab
    import webbrowser
    print('VeriNest is running at', url)
    webbrowser.open(url)
    _wait_idle()


def selftest():
    import json
    ok_all = True
    with tempfile.TemporaryDirectory() as tmp:
        core.PROJECTS = os.path.join(tmp, 'projects')
        core.WORKSPACE = tmp
        core.ensure_workspace()
        print('VeriNest %s self-test' % __version__)
        st = core.tool_status()
        for k, v in st.items():
            print('  %-10s %s' % (k, v['version'] or 'NOT FOUND'))
        if not st['iverilog']['path']:
            print('\nIcarus Verilog is missing: sudo apt install iverilog')
            return 1
        print()
        for ex in core.list_examples():
            name, meta = core.open_example(ex['id'])
            r = core.simulate(name, meta.get('top'))
            lint = core.lint(name)
            errs = [d for d in lint['diagnostics'] if d['severity'] == 'error']
            warns = [d for d in lint['diagnostics'] if d['severity'] != 'error']
            status = 'PASS' if r.get('passed') else 'FAIL'
            if status != 'PASS':
                ok_all = False
            print('  [%s] %-28s %5.2fs  lint: %d errors, %d warnings%s' % (
                status, ex['id'], r.get('elapsed', 0), len(errs), len(warns),
                '' if r.get('vcd') else '  (no waveform!)'))
            if status != 'PASS' or errs:
                for d in r.get('diagnostics', []) + errs:
                    print('        %s:%d: %s' % (d['file'], d['line'], d['message']))
                if r.get('error'):
                    print('        ' + r['error'])
                tail = (r.get('stdout') or '').strip().splitlines()[-8:]
                for line in tail:
                    print('        > ' + line)
            for d in warns:
                print('        warning %s:%d: [%s] %s' % (d['file'], d['line'], d.get('code', ''), d['message']))
    print('\nALL EXAMPLES PASSED' if ok_all else '\nSOME EXAMPLES FAILED')
    return 0 if ok_all else 1


def main():
    ap = argparse.ArgumentParser(prog='verinest', description='VeriNest - Verilog learning IDE')
    ap.add_argument('--browser', action='store_true', help='open in the default browser')
    ap.add_argument('--serve', action='store_true', help='run the server only')
    ap.add_argument('--port', type=int, default=0)
    ap.add_argument('--selftest', action='store_true', help='run all examples and report')
    ap.add_argument('--version', action='version', version='VeriNest ' + __version__)
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    srv = server.start(a.port)
    if a.serve:
        print('VeriNest running at', _url(srv), flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return
    run_window(srv, a.browser)
    srv.shutdown()


if __name__ == '__main__':
    main()
