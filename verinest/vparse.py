"""Lightweight Verilog-2005 structure parser.

Not a full parser: it extracts what VeriNest needs for the UI —
modules, parameters, ports, instances and declared identifiers.
"""
import ast
import operator
import re

KEYWORDS = set("""
always and assign automatic begin buf bufif0 bufif1 case casex casez cell cmos config deassign
default defparam design disable edge else end endcase endconfig endfunction endgenerate endmodule
endprimitive endspecify endtable endtask event for force forever fork function generate genvar
highz0 highz1 if ifnone incdir include initial inout input instance integer join large liblist
library localparam macromodule medium module nand negedge nmos nor noshowcancelled not notif0
notif1 or output parameter pmos posedge primitive pull0 pull1 pulldown pullup pulsestyle_onevent
pulsestyle_ondetect rcmos real realtime reg release repeat rnmos rpmos rtran rtranif0 rtranif1
scalared showcancelled signed small specify specparam strong0 strong1 supply0 supply1 table task
time tran tranif0 tranif1 tri tri0 tri1 triand trior trireg unsigned use uwire vectored wait wand
weak0 weak1 while wire wor xnor xor
""".split())


def strip_comments(text):
    """Replace comments with spaces (keeps offsets and line numbers). Strings are kept."""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"' and text[j] != '\n':
                if text[j] == '\\':
                    j += 1
                j += 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith('//', i):
            j = text.find('\n', i)
            if j < 0:
                j = n
            out.append(' ' * (j - i))
            i = j
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(''.join('\n' if ch == '\n' else ' ' for ch in text[i:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def blank_strings(text):
    return re.sub(r'"(?:\\.|[^"\\\n])*"', lambda m: '"' + ' ' * (len(m.group(0)) - 2) + '"', text)


def _balanced(text, i, open_ch='(', close_ch=')'):
    """text[i] == open_ch. Return index just after matching close."""
    depth = 0
    n = len(text)
    while i < n:
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _split_top(text, sep=','):
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    if ''.join(cur).strip():
        parts.append(''.join(cur))
    return parts


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.FloorDiv: operator.floordiv, ast.Div: operator.floordiv, ast.Mod: operator.mod,
        ast.Pow: operator.pow, ast.LShift: operator.lshift, ast.RShift: operator.rshift}


def safe_eval(expr, env):
    expr = expr.strip()
    expr = re.sub(r"(\d+)?'[sS]?[dD](\d+)", r'\2', expr)
    expr = re.sub(r"(\d+)?'[sS]?[hH]([0-9a-fA-F_]+)", lambda m: str(int(m.group(2).replace('_', ''), 16)), expr)
    expr = re.sub(r"(\d+)?'[sS]?[bB]([01_]+)", lambda m: str(int(m.group(2).replace('_', ''), 2)), expr)
    expr = expr.replace('/', '//').replace('////', '//')
    expr = re.sub(r'\$clog2\s*\(', 'clog2(', expr)
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError:
        return None

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            v = env.get(node.id)
            if v is None:
                raise ValueError
            return v
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'clog2' and len(node.args) == 1:
            v = ev(node.args[0])
            return max(0, (v - 1).bit_length())
        raise ValueError
    try:
        return ev(tree)
    except Exception:
        return None


def range_width(rng, env):
    if not rng:
        return 1
    m = re.match(r'\[\s*(.+?)\s*:\s*(.+?)\s*\]$', rng.strip())
    if not m:
        return None
    a, b = safe_eval(m.group(1), env), safe_eval(m.group(2), env)
    if a is None or b is None:
        return None
    return abs(a - b) + 1


DECL_RE = re.compile(
    r'^\s*(input|output|inout)\b\s*(wire|reg|integer|tri|signed)?\s*(signed)?\s*(\[[^\]]+\])?\s*(.*)$', re.S)


def _parse_params(text, env, params):
    for item in _split_top(text):
        item = item.strip()
        item = re.sub(r'^(parameter|localparam)\b', '', item).strip()
        item = re.sub(r'^(integer|signed|real)\b', '', item).strip()
        item = re.sub(r'^\[[^\]]*\]', '', item).strip()
        m = re.match(r'(\w+)\s*=\s*(.+)$', item, re.S)
        if m:
            name, val = m.group(1), ' '.join(m.group(2).split())
            params.append({'name': name, 'value': val})
            v = safe_eval(val, env)
            if v is not None:
                env[name] = v


def parse_file(text, filename=''):
    clean = strip_comments(text)
    clean_ns = blank_strings(clean)
    modules = []
    for m in re.finditer(r'\b(module|macromodule)\s+(\w+)', clean_ns):
        name = m.group(2)
        start = m.start()
        line = clean_ns.count('\n', 0, start) + 1
        i = m.end()
        n = len(clean_ns)
        while i < n and clean_ns[i].isspace():
            i += 1
        params, env = [], {}
        if i < n and clean_ns[i] == '#':
            i += 1
            while i < n and clean_ns[i].isspace():
                i += 1
            if i < n and clean_ns[i] == '(':
                j = _balanced(clean_ns, i)
                _parse_params(clean_ns[i + 1:j - 1], env, params)
                i = j
            while i < n and clean_ns[i].isspace():
                i += 1
        port_text = ''
        if i < n and clean_ns[i] == '(':
            j = _balanced(clean_ns, i)
            port_text = clean_ns[i + 1:j - 1]
            i = j
        endm = re.compile(r'\bendmodule\b').search(clean_ns, i)
        end = endm.end() if endm else n
        body = clean_ns[i:endm.start() if endm else n]
        end_line = clean_ns.count('\n', 0, end) + 1
        # body parameters
        for pm in re.finditer(r'\b(parameter|localparam)\b([^;]*);', body):
            _parse_params(pm.group(2), env, params if pm.group(1) == 'parameter' else [])
            if pm.group(1) == 'localparam':
                _parse_params(pm.group(2), env, [])
        ports = []
        port_items = [p.strip() for p in _split_top(port_text)] if port_text.strip() else []
        ansi = any(re.match(r'(input|output|inout)\b', p) for p in port_items)
        if ansi:
            cur = None
            for p in port_items:
                dm = DECL_RE.match(p)
                if dm:
                    cur = {'dir': dm.group(1), 'type': dm.group(2) if dm.group(2) != 'signed' else '',
                           'signed': bool(dm.group(3) or dm.group(2) == 'signed'), 'range': dm.group(4) or ''}
                    nm = dm.group(5).strip()
                else:
                    nm = p
                nm = nm.split('=')[0].strip()
                nm = re.sub(r'\[.*$', '', nm).strip()
                if cur and re.match(r'^\w+$', nm):
                    ports.append(dict(cur, name=nm))
        else:
            names = [re.sub(r'\[.*$', '', p).strip() for p in port_items]
            decls = {}
            for dm in re.finditer(r'\b(input|output|inout)\b([^;]*);', body):
                sub = DECL_RE.match(dm.group(0)[:-1])
                if not sub:
                    continue
                info = {'dir': sub.group(1), 'type': sub.group(2) if sub.group(2) != 'signed' else '',
                        'signed': bool(sub.group(3) or sub.group(2) == 'signed'), 'range': sub.group(4) or ''}
                for nm in _split_top(sub.group(5)):
                    nm = nm.split('=')[0].strip()
                    if re.match(r'^\w+$', nm):
                        decls[nm] = info
            for rm in re.finditer(r'\breg\b\s*(signed)?\s*(\[[^\]]+\])?\s*([^;]*);', body):
                for nm in _split_top(rm.group(3)):
                    nm = nm.split('=')[0].strip()
                    if nm in decls and not decls[nm]['type']:
                        decls[nm] = dict(decls[nm], type='reg')
            for nm in names:
                if nm in decls:
                    ports.append(dict(decls[nm], name=nm))
                elif nm:
                    ports.append({'dir': 'inout', 'type': '', 'signed': False, 'range': '', 'name': nm})
        for p in ports:
            p['range'] = ' '.join(p['range'].split())
            p['width'] = range_width(p['range'], env)
        # instances
        instances = []
        for im in re.finditer(r'(?:^|;|\bbegin\b(?:\s*:\s*\w+)?|\bend\b|\bendcase\b|\belse\b|\))\s*(\w+)\s*'
                              r'(#\s*\((?:[^()]|\([^()]*\))*\))?\s*(\w+)\s*(\[[^\]]*\])?\s*\(', body, re.M):
            mod, inst = im.group(1), im.group(3)
            if mod in KEYWORDS or inst in KEYWORDS:
                continue
            instances.append({'module': mod, 'name': inst})
        # identifiers declared in module
        idents = set(p['name'] for p in ports) | set(p['name'] for p in params)
        for dm in re.finditer(r'\b(wire|reg|integer|genvar|localparam|parameter|real|time|event)\b\s*(signed)?\s*(\[[^\]]+\])?\s*([^;]*);', body):
            for nm in _split_top(dm.group(4)):
                nm = re.sub(r'\[.*$', '', nm.split('=')[0]).strip()
                if re.match(r'^[A-Za-z_]\w*$', nm):
                    idents.add(nm)
        for fm in re.finditer(r'\b(function|task)\b\s*(?:automatic\s+)?(?:\[[^\]]+\]\s*)?(?:integer\s+|signed\s+)?(\w+)', body):
            idents.add(fm.group(2))
        has_initial = re.search(r'\binitial\b', body) is not None
        modules.append({
            'name': name, 'file': filename, 'line': line, 'end_line': end_line,
            'params': params, 'ports': ports, 'instances': instances,
            'identifiers': sorted(idents),
            'is_tb': (not ports) and has_initial,
        })
    return modules


def parse_project(files):
    """files: {path: text}. Returns modules + suggested top."""
    mods = []
    for path, text in files.items():
        if path.endswith(('.v', '.vh', '.sv')):
            try:
                mods.extend(parse_file(text, path))
            except Exception:
                pass
    used = {i['module'] for m in mods for i in m['instances']}
    names = {m['name'] for m in mods}
    for m in mods:
        m['is_top'] = m['name'] not in used
        m['instances'] = [i for i in m['instances'] if i['module'] in names or True]
    return mods


def guess_top(mods, current_file=None):
    tbs = [m for m in mods if m['is_tb'] and m['is_top']]
    if current_file:
        here = [m for m in tbs if m['file'] == current_file]
        if here:
            return here[0]['name']
    if tbs:
        return tbs[0]['name']
    tops = [m for m in mods if m['is_top']]
    return tops[0]['name'] if tops else (mods[0]['name'] if mods else None)
