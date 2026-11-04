"""Rule-based Verilog code formatter ("Clean Code").

Re-indents, normalises spacing after keywords, aligns declaration blocks,
trims trailing whitespace and collapses repeated blank lines.
It only changes whitespace, never tokens, so it cannot break your code.
"""
import re

from .vparse import strip_comments, blank_strings

OPEN_WORDS = re.compile(r'\b(begin|case|casez|casex|fork|function|task|generate|specify)\b')
CLOSE_WORDS = re.compile(r'\b(end|endcase|join|endfunction|endtask|endgenerate|endspecify)\b')
STARTS_CLOSE = re.compile(r'^(end|endcase|join|endfunction|endtask|endgenerate|endspecify|endmodule)\b')
HANG = re.compile(r'^(if|else|for|while|repeat|forever|always|initial)\b')
DIRECTIVE = re.compile(r'^`(timescale|define|include|ifdef|ifndef|else|elsif|endif|undef|celldefine|endcelldefine|'
                       r'default_nettype|resetall|line|pragma)\b')
DECL = re.compile(r'^(input|output|inout|wire|reg|parameter|localparam)\b')


def _code_part(line):
    """Return the line with comments and string contents blanked (same length)."""
    return blank_strings(strip_comments(line))


def _norm_spacing(line):
    if '"' in line or '/*' in line:
        return line
    cut = line.find('//')
    if cut < 0:
        cut = len(line)
    code_head, tail = line[:cut], line[cut:]
    code_head = re.sub(r'\b(if|for|while|case|casez|casex|repeat)\(', r'\1 (', code_head)
    code_head = re.sub(r'\b(always|initial)@', r'\1 @', code_head)
    code_head = re.sub(r'@\s+\(', '@(', code_head)
    code_head = re.sub(r'\)begin\b', ') begin', code_head)
    code_head = re.sub(r'\bend\s*else\b', 'end else', code_head)
    code_head = re.sub(r',(?=\S)', ', ', code_head)
    code_head = re.sub(r'\s+;', ';', code_head)
    code_head = re.sub(r'\s+,', ',', code_head)
    return code_head + tail


def _split_decl(code):
    m = re.match(r'^(input|output|inout|wire|reg|integer|parameter|localparam)\b\s*'
                 r'((?:wire|reg|integer|signed|unsigned)\b\s*)*?'
                 r'(\[[^\]]*\])?\s*(.*)$', code)
    if not m:
        return None
    kw = m.group(1)
    rest = code[len(kw):].lstrip()
    types = []
    while True:
        t = re.match(r'(wire|reg|integer|signed|unsigned)\b\s*', rest)
        if not t:
            break
        types.append(t.group(1))
        rest = rest[t.end():]
    rng = ''
    r = re.match(r'(\[[^\]]*\])\s*', rest)
    if r:
        rng = re.sub(r'\s+', '', r.group(1))
        rng = rng.replace(':', ':')
        rest = rest[r.end():]
    return kw, ' '.join(types), rng, rest


def _align_block(block, indent_str):
    parts = []
    for line in block:
        p = _split_decl(line)
        if p is None:
            return block
        parts.append(p)
    w_kw = max(len(p[0]) for p in parts)
    w_ty = max(len(p[1]) for p in parts)
    w_rg = max(len(p[2]) for p in parts)
    out = []
    for kw, ty, rg, rest in parts:
        s = kw.ljust(w_kw)
        if w_ty:
            s += ' ' + ty.ljust(w_ty)
        if w_rg:
            s += " " + rg.ljust(w_rg)
        s += ' ' + rest
        out.append(re.sub(r'\s+$', '', s))
    return out


def format_verilog(text, indent=4, align=True):
    lines = text.replace('\t', ' ' * indent).split('\n')
    out = []
    level = 0          # block nesting
    paren = 0          # open parentheses carried across lines
    hang = 0           # one-shot indent for single statement if/else/for
    in_block_comment = False
    module_header = False
    blank_run = 0
    stmt_open = False  # previous statement continues on this line
    for raw in lines:
        stripped = raw.strip()
        if in_block_comment:
            out.append(raw.rstrip())
            if '*/' in raw:
                in_block_comment = False
            continue
        if not stripped:
            blank_run += 1
            if blank_run <= 1:
                out.append('')
            continue
        blank_run = 0
        if DIRECTIVE.match(stripped):
            out.append(stripped)
            continue
        stripped = _norm_spacing(stripped)
        code = _code_part(stripped).strip()
        if stripped.startswith('/*') and '*/' not in stripped:
            in_block_comment = True

        cur = level
        if STARTS_CLOSE.match(code):
            cur = max(0, level - 1)
            hang = 0
        if code.startswith(')') and paren > 0:
            line_indent = cur + paren - 1
        else:
            line_indent = cur + paren
        if hang and not code.startswith('begin'):
            line_indent += hang
        elif stmt_open and paren == 0 and not hang:
            line_indent += 1
        spaces = indent * line_indent
        orig = len(raw.replace('\t', ' ' * indent)) - len(raw.replace('\t', ' ' * indent).lstrip())
        if (paren > 0 or (stmt_open and not hang)) and not code.startswith(')') and orig > spaces:
            spaces = orig      # keep the user's manual alignment of continuation lines
        out.append(' ' * spaces + stripped)

        # ---- update state for the next line ----
        opens = len(OPEN_WORDS.findall(code))
        closes = len(CLOSE_WORDS.findall(code))
        # 'begin' on a hanging line consumes the hang
        if hang and code.startswith('begin'):
            level += 0
        if re.match(r'^(module|macromodule)\b', code):
            module_header = True
        if re.search(r'\bendmodule\b', code):
            level = 0
            module_header = False
        net = opens - closes
        if STARTS_CLOSE.match(code):
            pass
        level = max(0, level + net)
        p_open = code.count('(') - code.count(')')
        paren = max(0, paren + p_open)
        if module_header and paren == 0 and code.endswith(';'):
            module_header = False
            level += 1
        # hanging single statement
        if HANG.match(code) or re.match(r'^end\s+else\b', code) or re.search(r'\belse(\s+if\s*\(.*\))?$', code):
            if not re.search(r'\bbegin\b', code) and not code.endswith(';') and paren == 0:
                hang = 1
            else:
                hang = 0
        elif re.match(r'^[^;]*:\s*$', code) and not code.startswith('default') or re.match(r'^default\s*:\s*$', code):
            hang = 1   # case item with statement on next line
        elif paren == 0:
            hang = 0
        if code:
            stmt_open = (paren == 0 and not hang and not module_header and
                         not re.search(r'(;|\bbegin|\bend|\bendcase|\bendmodule|\bendfunction|\bendtask|'
                                       r'\bendgenerate|\bgenerate|\bjoin|\bfork|:|\belse)\s*$', code) and
                         not OPEN_WORDS.search(code) and not CLOSE_WORDS.search(code))
    # trim trailing blank lines
    while out and out[-1] == '':
        out.pop()
    if align:
        out = _align_decls(out)
    return '\n'.join(out) + '\n'


def _align_decls(lines):
    res = []
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if DECL.match(s) and '//' not in s and '/*' not in s:
            ind = line[:len(line) - len(line.lstrip())]
            block = [s]
            j = i + 1
            while j < len(lines):
                t = lines[j].strip()
                tind = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
                if DECL.match(t) and '//' not in t and '/*' not in t and tind == ind:
                    block.append(t)
                    j += 1
                else:
                    break
            if len(block) > 1:
                block = _align_block(block, ind)
            res.extend(ind + b for b in block)
            i = j
        else:
            res.append(line)
            i += 1
    return res
