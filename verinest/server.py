"""Local HTTP server: serves the UI and a small JSON API (127.0.0.1 only)."""
import json
import mimetypes
import os
import secrets
import threading
import time
import traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from . import core, vparse, formatter, tbgen, __version__

WEB_DIR = os.path.join(core.APP_DIR, 'web')
TOKEN = secrets.token_urlsafe(16)
LAST_PING = [time.time()]

mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('image/svg+xml', '.svg')


def api(method, path, q, body):
    b = body or {}
    if path == '/api/ping':
        LAST_PING[0] = time.time()
        return {'ok': True}
    if path == '/api/state':
        return {'version': __version__, 'workspace': core.WORKSPACE, 'tools': core.tool_status(),
                'settings': core.load_settings()}
    if path == '/api/settings':
        return core.save_settings(b)
    if path == '/api/projects':
        return {'projects': core.list_projects()}
    if path == '/api/project/create':
        return {'name': core.create_project(b.get('name', 'project'))}
    if path == '/api/project/delete':
        core.delete_path(b['project'])
        return {'ok': True}
    if path == '/api/project/rename':
        return {'name': core.rename_project(b['project'], b['name'])}
    if path == '/api/file':
        return {'content': core.read_file(q['project'], q['path'])}
    if path == '/api/file/save':
        core.write_file(b['project'], b['path'], b['content'])
        return {'ok': True}
    if path == '/api/file/create':
        p = core.project_path(b['project'], b['path'])
        if os.path.exists(p):
            raise ValueError('File already exists')
        core.write_file(b['project'], b['path'], b.get('content', ''))
        return {'ok': True}
    if path == '/api/file/delete':
        core.delete_path(b['project'], b['path'])
        return {'ok': True}
    if path == '/api/file/rename':
        core.rename_path(b['project'], b['path'], b['new_path'])
        return {'ok': True}
    if path == '/api/examples':
        return {'examples': core.list_examples()}
    if path == '/api/examples/open':
        name, meta = core.open_example(b['id'])
        return {'name': name, 'meta': meta}
    if path == '/api/lint':
        return core.lint(b['project'], b.get('files'))
    if path == '/api/modules':
        files = core.project_sources(b['project'], b.get('files'))
        return {'modules': vparse.parse_project(files)}
    if path == '/api/simulate':
        return core.simulate(b['project'], b.get('top'), b.get('files'), b.get('current'))
    if path == '/api/vcd':
        return core.load_vcd(q['project'], q['path'])
    if path == '/api/format':
        return {'content': formatter.format_verilog(b['content'], int(b.get('indent', 4)))}
    if path == '/api/selftest':
        lines = []
        code = core.run_selftest(lines.append, __version__)
        return {'ok': code == 0, 'report': '\n'.join(lines)}
    if path == '/api/tbgen':
        mods = vparse.parse_file(b['content'], b.get('file', ''))
        mods = [m for m in mods if m['ports']]
        if b.get('module'):
            mods = [m for m in mods if m['name'] == b['module']] or mods
        if not mods:
            raise ValueError('No module with ports found in this file.')
        fn, text = tbgen.generate(mods[0])
        text = formatter.format_verilog(text)
        return {'filename': fn, 'content': text, 'module': mods[0]['name']}
    raise KeyError(path)


class Handler(BaseHTTPRequestHandler):
    server_version = 'VeriNest'

    def log_message(self, fmt, *args):
        if os.environ.get('VERINEST_DEBUG'):
            super().log_message(fmt, *args)

    def _send(self, code, data, ctype='application/json'):
        if not isinstance(data, (bytes, bytearray)):
            data = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method):
        u = urlparse(self.path)
        if u.path.startswith('/api/'):
            if self.headers.get('X-Token') != TOKEN:
                return self._send(403, {'error': 'forbidden'})
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            body = None
            if method == 'POST':
                n = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(n) or b'{}')
            try:
                return self._send(200, api(method, u.path, q, body))
            except KeyError as e:
                return self._send(404, {'error': 'unknown endpoint %s' % e})
            except (ValueError, FileNotFoundError, FileExistsError) as e:
                return self._send(400, {'error': str(e)})
            except Exception as e:  # noqa
                traceback.print_exc()
                return self._send(500, {'error': str(e)})
        # static files
        rel = u.path.lstrip('/') or 'index.html'
        p = os.path.realpath(os.path.join(WEB_DIR, rel))
        if not p.startswith(os.path.realpath(WEB_DIR)) or not os.path.isfile(p):
            return self._send(404, b'not found', 'text/plain')
        ctype = mimetypes.guess_type(p)[0] or 'application/octet-stream'
        with open(p, 'rb') as f:
            data = f.read()
        if rel == 'index.html':
            data = data.replace(b'__TOKEN__', TOKEN.encode())
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store' if rel == 'index.html' or not rel.startswith('vendor') else 'max-age=86400')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._handle('GET')

    def do_POST(self):
        self._handle('POST')


def start(port=0):
    core.ensure_workspace()
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    srv.daemon_threads = True
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv
