"""Workspace, project files and tool runners (Icarus Verilog, Verilator)."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
import time

from . import explain, vparse
from .vcd import parse_vcd

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_DIR = os.path.join(APP_DIR, 'examples')
WORKSPACE = os.environ.get('VERINEST_HOME', os.path.expanduser('~/VeriNest'))
PROJECTS = os.path.join(WORKSPACE, 'projects')
CONFIG = os.path.join(WORKSPACE, 'settings.json')

TEXT_EXT = ('.v', '.vh', '.sv', '.txt', '.md', '.hex', '.mem', '.bin', '.dat', '.vcd', '.json')
SIM_TIMEOUT = float(os.environ.get('VERINEST_SIM_TIMEOUT', '10'))
MAX_OUTPUT = 200_000


IS_WIN = os.name == 'nt'
NO_WINDOW = 0x08000000 if IS_WIN else 0     # CREATE_NO_WINDOW: no console flashes on Windows


def _bundled_dirs():
    """Icarus Verilog shipped next to VeriNest (Windows build), then common install places."""
    roots = [APP_DIR, os.path.dirname(os.path.abspath(sys.executable))]
    dirs = [os.path.join(r, 'iverilog', 'bin') for r in roots]
    if IS_WIN:
        dirs += [r'C:\iverilog\bin', r'C:\Program Files\iverilog\bin']
    return [d for d in dirs if os.path.isdir(d)]


# make bundled tools visible to every subprocess (vvp needs its own folder on PATH on Windows)
for _d in reversed(_bundled_dirs()):
    if _d not in os.environ.get('PATH', ''):
        os.environ['PATH'] = _d + os.pathsep + os.environ.get('PATH', '')


def which(name):
    return shutil.which(name)


def run(cmd, **kw):
    """subprocess.run with UTF-8 text and no console window on Windows."""
    return subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace',
                          creationflags=NO_WINDOW, **kw)


def read_text(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def tool_status():
    st = {}
    for t in ('iverilog', 'vvp', 'verilator'):
        p = which(t)
        ver = ''
        if p:
            try:
                arg = '-V' if t == 'iverilog' else ('--version' if t == 'verilator' else '-V')
                out = run([p, arg], timeout=5)
                txt = (out.stdout or out.stderr).strip().splitlines()
                ver = txt[0] if txt else ''
            except Exception:
                pass
        st[t] = {'path': p, 'version': ver}
    return st


# ---------------------------------------------------------------- projects
def ensure_workspace():
    os.makedirs(PROJECTS, exist_ok=True)


def safe_name(name):
    name = re.sub(r'[^\w\-. ]', '', name or '').strip().replace(' ', '_')
    return name[:64]


def project_path(project, rel=''):
    base = os.path.realpath(os.path.join(PROJECTS, safe_name(project)))
    if not base.startswith(os.path.realpath(PROJECTS) + os.sep):
        raise ValueError('bad project')
    p = os.path.realpath(os.path.join(base, rel)) if rel else base
    if p != base and not p.startswith(base + os.sep):
        raise ValueError('bad path')
    return p


def list_projects():
    ensure_workspace()
    res = []
    for name in sorted(os.listdir(PROJECTS), key=str.lower):
        p = os.path.join(PROJECTS, name)
        if not os.path.isdir(p) or name.startswith('.'):
            continue
        files = []
        for dp, dns, fns in os.walk(p):
            dns[:] = [d for d in dns if not d.startswith('.')]
            for fn in sorted(fns):
                if fn.startswith('.'):
                    continue
                rel = os.path.relpath(os.path.join(dp, fn), p).replace(os.sep, '/')
                files.append(rel)
        res.append({'name': name, 'files': sorted(files, key=_file_sort), 'mtime': os.path.getmtime(p)})
    return res


def _file_sort(f):
    order = 0 if f.endswith('.v') and not os.path.basename(f).startswith('tb') else \
        1 if f.endswith('.v') else 2 if f.endswith('.vcd') else 3
    return (order, f.lower())


def unique_project_name(base):
    base = safe_name(base) or 'project'
    name, k = base, 2
    while os.path.exists(os.path.join(PROJECTS, name)):
        name = '%s_%d' % (base, k)
        k += 1
    return name


NEW_MODULE = """`timescale 1ns / 1ps

module {name} (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] a,
    output reg  [7:0] y
);

    always @(posedge clk) begin
        if (rst)
            y <= 8'd0;
        else
            y <= a;
    end

endmodule
"""


def create_project(name):
    ensure_workspace()
    name = unique_project_name(name)
    p = os.path.join(PROJECTS, name)
    os.makedirs(p)
    mod = re.sub(r'\W', '_', name).lower()
    if not re.match(r'[a-z_]', mod):
        mod = 'm_' + mod
    write_text(os.path.join(p, mod + '.v'), NEW_MODULE.format(name=mod))
    return name


def read_file(project, rel):
    return read_text(project_path(project, rel))


def write_file(project, rel, content):
    p = project_path(project, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    write_text(p, content)


def delete_path(project, rel=''):
    """Move to ~/VeriNest/.trash instead of deleting permanently."""
    p = project_path(project, rel)
    trash = os.path.join(WORKSPACE, '.trash', time.strftime('%Y%m%d-%H%M%S'))
    os.makedirs(trash, exist_ok=True)
    shutil.move(p, os.path.join(trash, os.path.basename(p)))


def rename_path(project, rel, new_rel):
    src = project_path(project, rel)
    dst = project_path(project, new_rel)
    if os.path.exists(dst):
        raise ValueError('A file with that name already exists')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.rename(src, dst)


def rename_project(project, new_name):
    new_name = safe_name(new_name)
    if not new_name:
        raise ValueError('Invalid name')
    src = project_path(project)
    dst = os.path.join(PROJECTS, new_name)
    if os.path.exists(dst):
        raise ValueError('A project with that name already exists')
    os.rename(src, dst)
    return new_name


def project_sources(project, overrides=None):
    """All Verilog sources of a project, with unsaved editor buffers applied."""
    base = project_path(project)
    files = {}
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if not d.startswith('.')]
        for fn in fns:
            if fn.endswith(('.v', '.vh', '.sv')) and not fn.startswith('.'):
                rel = os.path.relpath(os.path.join(dp, fn), base)
                files[rel.replace(os.sep, '/')] = read_text(os.path.join(dp, fn))
    for k, v in (overrides or {}).items():
        if k.endswith(('.v', '.vh', '.sv')):
            files[k] = v
    return files


# ---------------------------------------------------------------- examples
def list_examples():
    res = []
    if not os.path.isdir(EXAMPLES_DIR):
        return res
    for name in sorted(os.listdir(EXAMPLES_DIR)):
        p = os.path.join(EXAMPLES_DIR, name)
        meta_p = os.path.join(p, 'example.json')
        if os.path.isfile(meta_p):
            meta = json.loads(read_text(meta_p))
            meta['id'] = name
            meta['files'] = sorted([x for x in os.listdir(p) if x != 'example.json'], key=_file_sort)
            res.append(meta)
    return res


def open_example(ex_id):
    ensure_workspace()
    src = os.path.join(EXAMPLES_DIR, os.path.basename(ex_id))
    if not os.path.isdir(src):
        raise ValueError('Unknown example')
    meta = json.loads(read_text(os.path.join(src, 'example.json')))
    name = unique_project_name(meta.get('project', ex_id))
    shutil.copytree(src, os.path.join(PROJECTS, name), ignore=shutil.ignore_patterns('example.json'))
    return name, meta


# ---------------------------------------------------------------- tools
def _stage(files, workdir, cwd=None):
    """Write sources into workdir.

    Returns the source paths *relative to cwd* (the tools run with that working
    directory, so their messages contain short paths without drive letters) and a
    map from every spelling of a path the tools may print back to the project file.
    """
    cwd = cwd or workdir
    paths, pmap = [], {}
    for rel, text in files.items():
        ap = os.path.join(workdir, *rel.split('/'))
        os.makedirs(os.path.dirname(ap), exist_ok=True)
        write_text(ap, text)
        rp = os.path.relpath(ap, cwd)
        if rel.endswith(('.v', '.sv')):
            paths.append(rp)
        for k in (ap, rp, rel, os.path.basename(rel)):
            pmap[k] = rel
            pmap[k.replace('\\', '/')] = rel
            pmap[k.replace('/', '\\')] = rel
    return paths, pmap


def lint(project, overrides=None):
    files = project_sources(project, overrides)
    mods = vparse.parse_project(files)
    tb_files = {m['file'] for m in mods if m['is_tb']}
    diags = []
    with tempfile.TemporaryDirectory(prefix='verinest-lint-') as wd:
        paths, pmap = _stage(files, wd)
        iv = which('iverilog')
        if iv and paths:
            try:
                r = run([iv, '-g2005', '-Wall', '-Wno-timescale', '-t', 'null', '-I', '.'] + paths, timeout=20, cwd=wd)
                diags += explain.parse_iverilog(r.stdout + '\n' + r.stderr, pmap)
            except subprocess.TimeoutExpired:
                pass
        vl = which('verilator')
        if vl and paths:
            try:
                r = run([vl, '--lint-only', '-Wall', '-Wno-fatal', '--timing', '-Wno-DECLFILENAME',
                                    '-Wno-MULTITOP', '-Wno-UNUSED', '-I.'] + paths, timeout=30, cwd=wd)
                out = r.stdout + '\n' + r.stderr
                if '--timing' in out and 'Invalid option' in out:   # verilator 4.x
                    r = run([vl, '--lint-only', '-Wall', '-Wno-fatal', '-Wno-DECLFILENAME',
                                        '-Wno-MULTITOP', '-Wno-UNUSED', '-Wno-STMTDLY', '-I.'] + paths, timeout=30, cwd=wd)
                    out = r.stdout + '\n' + r.stderr
                vd = explain.parse_verilator(out, pmap, tb_files)
                iv_err_lines = {(d['file'], d['line']) for d in diags if d['severity'] == 'error'}
                iv_err_files = {d['file'] for d in diags if d['severity'] == 'error'}
                for d in vd:
                    if d['severity'] == 'error':
                        if d['file'] in iv_err_files or (d['file'], d['line']) in iv_err_lines:
                            continue      # iverilog already reported an error here
                        if iv:
                            # iverilog (the simulator we actually use) accepted this file:
                            # verilator-only errors become warnings, and are skipped in testbenches
                            if d['file'] in tb_files or not d.get('code'):
                                continue
                            d['severity'] = 'warning'
                    diags.append(d)
            except subprocess.TimeoutExpired:
                pass
    for rel, text in files.items():
        sd = explain.structure_check(text, rel)
        has_err = any(d['file'] == rel and d['severity'] == 'error' for d in diags)
        if sd and (has_err or not which('iverilog')):
            for d in sd:
                diags.insert(0, d)
    diags = explain.enrich(diags, files)
    # de-duplicate
    seen, out = set(), []
    for d in diags:
        k = (d['file'], d['line'], d['message'])
        if k not in seen:
            seen.add(k)
            out.append(d)
    out.sort(key=lambda d: (d['file'], 0 if d['severity'] == 'error' else 1, d['line']))
    return {'diagnostics': out, 'modules': mods}


DUMP_STUB = """`timescale 1ns / 1ps
module __verinest_dump;
  initial begin
    $dumpfile("{vcd}");
    $dumpvars(0, {top});
  end
endmodule
"""


def simulate(project, top=None, overrides=None, current_file=None):
    t0 = time.time()
    files = project_sources(project, overrides)
    mods = vparse.parse_project(files)
    if not top:
        top = vparse.guess_top(mods, current_file)
    res = {'top': top, 'modules': mods, 'diagnostics': [], 'stdout': '', 'ok': False, 'vcd': None,
           'phase': 'compile'}
    iv, vvp = which('iverilog'), which('vvp')
    if not iv or not vvp:
        res['error'] = 'Icarus Verilog is not installed. Run: sudo apt install iverilog'
        return res
    if not top:
        res['error'] = 'No module found to simulate.'
        return res
    base = project_path(project)
    build = os.path.join(base, '.verinest')
    os.makedirs(build, exist_ok=True)
    # make sure the sim sees the same (possibly unsaved) sources
    stage = os.path.join(build, 'src')
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    paths, pmap = _stage(files, stage, cwd=base)
    top_mod = next((m for m in mods if m['name'] == top), None)
    has_dump = '$dumpvars' in (files.get(top_mod['file'], '') if top_mod else '') or \
        any('$dumpvars' in t for t in files.values())
    tops = ['-s', top]
    if not has_dump:
        stub = os.path.join(build, '__verinest_dump.v')
        # forward slashes: a backslash inside a Verilog string is an escape character
        write_text(stub, DUMP_STUB.format(vcd='.verinest/auto.vcd', top=top))
        paths.append('.verinest/__verinest_dump.v')
        tops += ['-s', '__verinest_dump']
    out_vvp = os.path.join('.verinest', 'sim.vvp')
    r = run([iv, '-g2005', '-Wall', '-Wno-timescale', '-o', out_vvp, '-I', '.verinest/src'] + tops + paths,
            timeout=30, cwd=base)
    comp_out = r.stdout + r.stderr
    res['diagnostics'] = explain.enrich(explain.parse_iverilog(comp_out, pmap), files)
    res['compile_output'] = comp_out.replace('.verinest/src/', '').replace('.verinest\\src\\', '')
    if r.returncode != 0:
        res['error'] = 'Compilation failed. See the Problems panel.'
        res['elapsed'] = round(time.time() - t0, 2)
        return res
    res['phase'] = 'run'
    try:
        p = run([vvp, '-n', out_vvp], timeout=SIM_TIMEOUT, cwd=base)
        out = p.stdout + p.stderr
        res['returncode'] = p.returncode
        res['ok'] = p.returncode == 0
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b'').decode(errors='replace') if isinstance(e.stdout, bytes) else (e.stdout or '')
        res['timeout'] = True
        res['error'] = ('Simulation stopped after %d s. Your testbench probably never calls $finish '
                        '(a free-running clock keeps the simulation alive forever).' % SIM_TIMEOUT)
    # show short file names instead of the internal staging path
    for prefix in (stage + os.sep, build + os.sep, base + os.sep, '.verinest/src/', '.verinest\\src\\',
                   '.verinest/', '.verinest\\'):
        out = out.replace(prefix, '')
        res['compile_output'] = res['compile_output'].replace(prefix, '')
    if len(out) > MAX_OUTPUT:
        out = out[:MAX_OUTPUT] + '\n... output truncated ...\n'
    res['stdout'] = out
    # locate VCD
    vcd = None
    if not has_dump:
        vcd = os.path.join(build, 'auto.vcd')
    else:
        cands = []
        for dp, dns, fns in os.walk(base):
            for fn in fns:
                if fn.endswith('.vcd'):
                    fp = os.path.join(dp, fn)
                    if os.path.getmtime(fp) >= t0 - 1:
                        cands.append(fp)
        if cands:
            vcd = max(cands, key=os.path.getmtime)
    if vcd and os.path.isfile(vcd) and os.path.getsize(vcd) > 0:
        try:
            res['vcd'] = parse_vcd(vcd)
            res['vcd_file'] = os.path.relpath(vcd, base).replace(os.sep, '/')
        except Exception as e:  # noqa
            res['vcd_error'] = str(e)
    res['elapsed'] = round(time.time() - t0, 2)
    res['passed'] = bool(re.search(r'\bPASS', out)) and not re.search(r'\b(FAIL|ERROR)', out)
    res['failed'] = bool(re.search(r'\b(FAIL|ERROR)', out))
    return res


def load_vcd(project, rel):
    return parse_vcd(project_path(project, rel))


# ---------------------------------------------------------------- self-test
def run_selftest(out, version=''):
    """Simulate every example in a throw-away workspace and report through out(line)."""
    global PROJECTS, WORKSPACE
    saved = (PROJECTS, WORKSPACE)
    ok_all = True
    tmp = tempfile.mkdtemp(prefix='verinest-selftest-')
    try:
        PROJECTS = os.path.join(tmp, 'projects')
        WORKSPACE = tmp
        ensure_workspace()
        out('VeriNest %s self-test' % version)
        st = tool_status()
        for k, v in st.items():
            out('  %-10s %s' % (k, v['version'] or 'NOT FOUND'))
        if not st['iverilog']['path']:
            out('')
            out('Icarus Verilog is missing: ' + ('reinstall VeriNest' if IS_WIN else 'sudo apt install iverilog'))
            return 1
        out('')
        for ex in list_examples():
            name, meta = open_example(ex['id'])
            r = simulate(name, meta.get('top'))
            lr = lint(name)
            errs = [d for d in lr['diagnostics'] if d['severity'] == 'error']
            warns = [d for d in lr['diagnostics'] if d['severity'] != 'error']
            status = 'PASS' if r.get('passed') else 'FAIL'
            if status != 'PASS':
                ok_all = False
            out('  [%s] %-28s %5.2fs  lint: %d errors, %d warnings%s' % (
                status, ex['id'], r.get('elapsed', 0), len(errs), len(warns),
                '' if r.get('vcd') else '  (no waveform!)'))
            if status != 'PASS' or errs:
                for d in r.get('diagnostics', []) + errs:
                    out('        %s:%d: %s' % (d['file'], d['line'], d['message']))
                if r.get('error'):
                    out('        ' + r['error'])
                tail = (r.get('stdout') or '').strip().splitlines()[-8:]
                for line in tail:
                    out('        > ' + line)
            for d in warns:
                out('        warning %s:%d: [%s] %s' % (d['file'], d['line'], d.get('code', ''), d['message']))
    finally:
        PROJECTS, WORKSPACE = saved
        shutil.rmtree(tmp, ignore_errors=True)
    out('')
    out('ALL EXAMPLES PASSED' if ok_all else 'SOME EXAMPLES FAILED')
    return 0 if ok_all else 1


# ---------------------------------------------------------------- settings
def load_settings():
    try:
        return json.loads(read_text(CONFIG))
    except Exception:
        return {}


def save_settings(s):
    ensure_workspace()
    cur = load_settings()
    cur.update(s or {})
    write_text(CONFIG, json.dumps(cur, indent=2))
    return cur
