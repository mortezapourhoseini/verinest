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


def _app_browsers():
    """Browsers that support --app (a standalone window), best first."""
    found = []
    if os.name == 'nt':
        env = os.environ
        roots = [env.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), env.get('ProgramFiles', r'C:\Program Files'),
                 env.get('LOCALAPPDATA', '')]
        rels = [r'Microsoft\Edge\Application\msedge.exe', r'Google\Chrome\Application\chrome.exe',
                r'BraveSoftware\Brave-Browser\Application\brave.exe']
        for rel in rels:            # Edge first: it is on every Windows 10/11
            for r in roots:
                p = os.path.join(r, rel) if r else ''
                if p and os.path.isfile(p) and p not in found:
                    found.append(p)
        for n in ('msedge', 'chrome'):
            p = shutil.which(n)
            if p and p not in found:
                found.append(p)
    else:
        for b in APP_BROWSERS:
            p = shutil.which(b)
            if p:
                found.append(p)
    return found


def _data_dir():
    if os.name == 'nt':
        return os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'VeriNest')
    return os.path.expanduser('~/.config/verinest')


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
        for exe in _app_browsers():
            profile = os.path.join(_data_dir(), 'window')
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
    return core.run_selftest(lambda line='': print(line, flush=True), __version__)


def main():
    # a windowed build (no console) has no stdout: log to a file instead
    if sys.stdout is None or sys.stderr is None:
        os.makedirs(_data_dir(), exist_ok=True)
        log = open(os.path.join(_data_dir(), 'verinest.log'), 'w', encoding='utf-8')
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log
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
