"""Minimal VCD (Value Change Dump) parser -> JSON-friendly dict."""
import os

MAX_CHANGES = 3_000_000


def parse_vcd(path):
    size = os.path.getsize(path)
    signals = {}      # code -> {name,width,type,paths:[...]}
    root = {'name': '', 'children': [], 'signals': []}
    stack = [root]
    timescale = '1ns'
    changes = {}
    t = 0
    end_time = 0
    n_changes = 0
    truncated = False
    in_defs = True

    with open(path, 'r', errors='replace') as f:
        data = f.read()
    tokens_iter = iter(data.split())
    for tok in tokens_iter:
        if in_defs:
            if tok == '$timescale':
                parts = []
                for x in tokens_iter:
                    if x == '$end':
                        break
                    parts.append(x)
                timescale = ''.join(parts)
            elif tok == '$scope':
                kind = next(tokens_iter)
                name = next(tokens_iter)
                next(tokens_iter)  # $end
                node = {'name': name, 'kind': kind, 'children': [], 'signals': []}
                stack[-1]['children'].append(node)
                stack.append(node)
            elif tok == '$upscope':
                next(tokens_iter)
                if len(stack) > 1:
                    stack.pop()
            elif tok == '$var':
                vtype = next(tokens_iter)
                width = int(next(tokens_iter))
                code = next(tokens_iter)
                ref = []
                for x in tokens_iter:
                    if x == '$end':
                        break
                    ref.append(x)
                name = ref[0] if ref else code
                if len(ref) > 1 and ref[1].startswith('['):
                    name += ref[1]
                path_name = '.'.join(n['name'] for n in stack[1:]) + '.' + name
                if code not in signals:
                    signals[code] = {'id': code, 'name': name, 'width': width, 'type': vtype, 'path': path_name}
                    changes[code] = []
                stack[-1]['signals'].append({'id': code, 'name': name, 'width': width, 'type': vtype,
                                             'path': path_name})
            elif tok == '$enddefinitions':
                next(tokens_iter)
                in_defs = False
            elif tok in ('$comment', '$date', '$version'):
                for x in tokens_iter:
                    if x == '$end':
                        break
            continue
        # value changes
        c = tok[0]
        if c == '#':
            try:
                t = int(tok[1:])
            except ValueError:
                continue
            if t > end_time:
                end_time = t
        elif c in '01xzXZ':
            code = tok[1:]
            lst = changes.get(code)
            if lst is not None:
                v = c.lower()
                if not lst or lst[-1][1] != v:
                    lst.append([t, v])
                    n_changes += 1
        elif c in 'bB':
            val = tok[1:].lower()
            code = next(tokens_iter)
            lst = changes.get(code)
            if lst is not None:
                w = signals[code]['width']
                if len(val) < w:
                    pad = val[0] if val[0] in 'xz' else '0'
                    val = pad * (w - len(val)) + val
                if not lst or lst[-1][1] != val:
                    lst.append([t, val])
                    n_changes += 1
        elif c in 'rR':
            val = tok[1:]
            code = next(tokens_iter)
            lst = changes.get(code)
            if lst is not None:
                signals[code]['real'] = True
                if not lst or lst[-1][1] != val:
                    lst.append([t, val])
                    n_changes += 1
        elif tok.startswith('$'):
            # $dumpvars / $dumpall / $end etc. are just wrappers
            continue
        if n_changes > MAX_CHANGES:
            truncated = True
            break
    if root['children'] and len(root['children']) == 1 and not root['signals']:
        scopes = root['children']
    else:
        scopes = root['children']
    return {'timescale': timescale, 'end': end_time, 'scopes': scopes, 'signals': signals,
            'changes': changes, 'truncated': truncated, 'size': size}
