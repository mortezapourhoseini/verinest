"""Turn raw tool messages into friendly, learner-oriented explanations."""
import re

from .vparse import strip_comments, blank_strings

# (pattern on message, title, explanation, how-to-fix)
RULES = [
    (r'syntax error',
     'Syntax error',
     'The compiler could not understand the code at (or just before) this line.',
     "Check the previous line for a missing ';', an unclosed '(' or '[', or a missing "
     "'end' / 'endcase' / 'endmodule'. Errors are often reported one line AFTER the real mistake."),
    (r'Unable to bind (?:wire/reg/memory|wire/reg|reg|wire|parameter)\s*`?([\w.]+)',
     'Undeclared name',
     "The name '{1}' is used here but it is never declared in this module.",
     "Declare it (e.g. 'wire [7:0] {1};' or 'reg {1};'), or fix the spelling. "
     "Remember Verilog names are case-sensitive."),
    (r'is not a valid l-value',
     'Cannot assign to a wire here',
     'Inside an always/initial block you can only assign to variables (reg / integer), not to wires.',
     "Declare the signal as 'reg' (e.g. 'output reg [7:0] y'), or drive it with a continuous "
     "'assign y = ...;' outside the always block."),
    (r'(?:cannot be driven by primitives or continuous assignment|reg .* cannot be driven)',
     'Cannot use assign on a reg',
     "A 'reg' can only be written inside always/initial blocks. 'assign' needs a wire.",
     "Either declare the signal as 'wire', or move the assignment into an always block."),
    (r'Unknown module type:\s*(\w+)',
     'Unknown module',
     "Module '{1}' is instantiated but no file in this project defines it.",
     "Check the spelling of the module name, or add the .v file that contains 'module {1}'."),
    (r"port ``?(\w+)'*\s+is not a port of\s+(\w+)",
     'Wrong port name',
     "'{1}' is not a port of module '{2}'.",
     "Open the definition of '{2}' and use one of its real port names in .{1}(...)."),
    (r'Port (\d+) \((\w+)\) of (\w+) expects (\d+) bits?, got (\d+)',
     'Port width mismatch',
     "Port '{2}' of '{3}' is {4} bit(s) wide but the signal connected to it is {5} bit(s).",
     'Make the connected signal the same width, or select bits explicitly (e.g. sig[3:0]). '
     'The extra bits are padded with zeros or silently cut off.'),
    (r'Padding (\d+) high bits of the port',
     'Port width mismatch (padding)',
     'The connected signal is narrower than the port, so the upper bits are filled with zeros.',
     'Use a signal of the same width as the port.'),
    (r'(?:has already been declared|already declared|duplicate declaration)',
     'Duplicate declaration',
     'This name is declared more than once in the same module.',
     'Remove one of the declarations. In ANSI-style port lists, do not declare the port again in the body.'),
    (r'Variable declaration in unnamed block requires SystemVerilog',
     'Declaration inside an unnamed block',
     'Verilog-2005 only allows declarations inside a begin...end block if the block has a name.',
     "Move the declaration to the module level, or name the block: 'begin : my_block'."),
    (r'(?:requires SystemVerilog|SystemVerilog)',
     'SystemVerilog feature',
     'This construct is SystemVerilog, but VeriNest compiles plain Verilog-2005.',
     "Use Verilog-2005 forms: 'reg'/'wire' instead of 'logic', 'always @(posedge clk)' "
     "instead of 'always_ff', 'always @(*)' instead of 'always_comb'."),
    (r'Some modules have no timescale|timescale',
     'Missing `timescale',
     'Some files have a `timescale and others do not, so delays like #10 may mean different things.',
     "Add '`timescale 1ns / 1ps' as the first line of every .v file."),
    (r'implicit definition of wire\s*.?(\w+)',
     'Implicit wire',
     "'{1}' was never declared, so Verilog silently created a 1-bit wire for it.",
     'Declare it explicitly with the right width. Implicit nets are a common source of 1-bit bugs.'),
    (r'Unknown (?:system task|system function|system task or function)\s*(\$\w+)',
     'Unknown system task',
     "'{1}' is not a system task that Icarus Verilog knows.",
     'Check the spelling: $display, $monitor, $finish, $dumpfile, $dumpvars, $random, $time...'),
    (r'Extra digits given for sized|numeric constant truncated|Unsized constant',
     'Constant does not fit',
     'The number has more digits than its declared size.',
     "Fix the size prefix, e.g. 4'b1010 has 4 bits, 8'hFF has 8 bits."),
    (r'(?:out of bound|out of range|is out of range|index .* out of)',
     'Index out of range',
     'A bit-select or array index is outside the declared range.',
     'Compare the index with the declaration, e.g. reg [7:0] r has bits r[7]..r[0].'),
    (r'Malformed statement|Incomprehensible|Invalid module item',
     'Statement not allowed here',
     'This statement is not valid at this place.',
     "Procedural statements (if, case, for, x = ...) must be inside 'always' or 'initial'. "
     "Module items (assign, always, instances) must be outside them."),
    (r'Unable to elaborate',
     'Cannot elaborate expression',
     'The compiler could not evaluate this expression (often an undeclared name or bad width).',
     'Check every name in the expression is declared and parameters have values.'),
    (r'Unknown module|instance .* not found',
     'Unknown module', 'A module used here was not found.', 'Add the file that defines it to the project.'),
]

VERILATOR_CODES = {
    'WIDTH': ('Width mismatch', 'The two sides of this operation/assignment have different bit widths.',
              "Make the widths match, or extend/cut explicitly, e.g. {4'b0, a} or a[3:0]."),
    'WIDTHEXPAND': ('Width mismatch (value extended)', 'A narrower value is being zero-extended to a wider one.',
                    "Make the widths match, e.g. use 8'd1 instead of 1 or {4'b0, a}."),
    'WIDTHTRUNC': ('Width mismatch (value truncated)', 'A wider value is being cut down; upper bits are lost.',
                   'Widen the destination, or take the bits you want explicitly, e.g. sum[7:0].'),
    'LATCH': ('Latch inferred', 'In this combinational block some signal is not assigned on every path, '
              'so the hardware must remember its old value (a latch).',
              "Assign every output in every branch: add an 'else', a 'default:' in case, "
              'or give default values at the top of the always @(*) block.'),
    'NOLATCH': ('Not a latch', 'always_latch did not produce a latch.', 'Use always @(*).'),
    'COMBDLY': ('Non-blocking in combinational logic', "'<=' is used inside a combinational always @(*) block.",
                "Use blocking '=' in always @(*) and non-blocking '<=' in always @(posedge clk)."),
    'BLKSEQ': ('Blocking assignment in sequential logic', "'=' is used inside a clocked always block.",
               "Use non-blocking '<=' for registers in always @(posedge clk) to avoid race conditions."),
    'BLKANDNBLK': ('Mixed = and <=', 'The same variable is written with both blocking and non-blocking assignments.',
                   'Pick one style per variable: <= for clocked logic, = for combinational logic.'),
    'CASEINCOMPLETE': ('Incomplete case', 'Not all values of the case expression are covered.',
                       "Add a 'default:' branch."),
    'CASEOVERLAP': ('Overlapping case items', 'Two case items match the same value; only the first one is used.',
                    'Remove or fix the duplicate item.'),
    'CASEX': ('casex used', 'casex treats x as don\'t care, which can hide bugs.', "Prefer 'casez' with '?'."),
    'IMPLICIT': ('Implicit wire', 'A signal is used without being declared, so a 1-bit wire was created.',
                 'Declare it with the correct width.'),
    'MULTIDRIVEN': ('Driven from several blocks', 'This signal is assigned in more than one always block.',
                    'Assign each signal from exactly one always block (or one assign).'),
    'UNDRIVEN': ('Signal never driven', 'This signal is read but nothing ever assigns a value to it.',
                 'Drive it with assign / always, or connect it to a module output.'),
    'UNOPTFLAT': ('Combinational loop', 'A combinational signal depends on itself (a loop).',
                  'Break the loop with a register, or check for a typo in the signal names.'),
    'PINMISSING': ('Unconnected port', 'An instance does not connect one of the module\'s ports.',
                   'Connect it, or write .port() to show it is intentionally left open.'),
    'PINCONNECTEMPTY': ('Empty port connection', 'A port is connected to nothing.', 'Connect it if needed.'),
    'INITIALDLY': ('Non-blocking in initial', "'<=' used inside an initial block.", "Use '=' in initial blocks."),
    'SELRANGE': ('Bit-select out of range', 'This bit-select is outside the declared range.',
                 'Check the index against the declaration.'),
    'SYNCASYNCNET': ('Reset used both sync and async', 'A reset is used both synchronously and asynchronously.',
                     'Use one reset style consistently.'),
    'STMTDLY': ('Delay in design', 'A #delay is used; it is ignored in synthesis.', 'Use delays only in testbenches.'),
    'DECLFILENAME': ('File name', 'Module name differs from file name.', 'Name the file <module>.v.'),
    'MULTITOP': ('Several top modules', 'More than one module is not instantiated by any other.', ''),
    'ASSIGNIN': ('Assigning to an input', 'An input port is being assigned inside the module.',
                 'Inputs are driven from outside; assign an internal signal or an output instead.'),
    'PROCASSWIRE': ('Cannot assign to a wire here', 'A wire is assigned inside an always/initial block.',
                    "Declare it as 'reg', or use 'assign' outside the always block."),
    'CONTASSREG': ('Cannot use assign on a reg', "'assign' drives a signal declared as reg.",
                   "Declare it as 'wire', or move the assignment into an always block."),
}

# Verilator warnings worth showing to a learner
VERILATOR_KEEP = {'WIDTH', 'WIDTHEXPAND', 'WIDTHTRUNC', 'LATCH', 'COMBDLY', 'BLKSEQ', 'BLKANDNBLK',
                  'CASEINCOMPLETE', 'CASEOVERLAP', 'IMPLICIT', 'MULTIDRIVEN', 'UNDRIVEN', 'UNOPTFLAT',
                  'PINMISSING', 'SELRANGE', 'SYNCASYNCNET', 'ASSIGNIN', 'PROCASSWIRE', 'CONTASSREG', 'CASEX'}
VERILATOR_TB_SKIP = {'WIDTH', 'WIDTHEXPAND', 'WIDTHTRUNC', 'BLKSEQ', 'UNDRIVEN', 'MULTIDRIVEN', 'CASEINCOMPLETE',
                     'BLKANDNBLK'}


def explain(message, source='iverilog', code=None):
    if source == 'verilator' and code:
        if code in VERILATOR_CODES:
            t, e, f = VERILATOR_CODES[code]
            return {'title': t, 'explain': e, 'fix': f}
    for pat, title, exp, fix in RULES:
        m = re.search(pat, message, re.I)
        if m:
            groups = [m.group(0)] + list(m.groups())

            def fmt(s):
                for k, g in enumerate(groups):
                    s = s.replace('{%d}' % k, g or '')
                return s
            return {'title': title, 'explain': fmt(exp), 'fix': fmt(fix)}
    return None


IV_RE = re.compile(r'^(?P<file>[^:\n]+?):(?P<line>\d+):\s*(?:(?P<sev>error|warning|sorry)\s*:\s*)?(?P<msg>.*)$')
VL_RE = re.compile(r'^%(?P<sev>Error|Warning)(?:-(?P<code>[A-Z0-9_]+))?:\s*(?P<file>[^:\n]+?):(?P<line>\d+):(?P<col>\d+):\s*(?P<msg>.*)$')


def parse_iverilog(output, path_map):
    diags = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith('I give up') or 'error(s) during elaboration' in line:
            continue
        m = IV_RE.match(line)
        if not m:
            continue
        f = path_map.get(m.group('file'))
        if f is None:
            continue
        sev = m.group('sev') or ('error' if 'syntax error' in m.group('msg') else 'warning')
        if sev == 'sorry':
            sev = 'error'
        msg = m.group('msg').strip().lstrip(':').strip()
        if msg.lower().startswith('errors in') or not msg:
            continue
        diags.append({'file': f, 'line': int(m.group('line')), 'col': 1, 'severity': sev,
                      'message': msg, 'source': 'iverilog'})
    return diags


def parse_verilator(output, path_map, tb_files=()):
    diags = []
    for raw in output.splitlines():
        m = VL_RE.match(raw.strip())
        if not m:
            continue
        f = path_map.get(m.group('file'))
        if f is None:
            continue
        code = m.group('code')
        sev = 'error' if m.group('sev') == 'Error' and not code else 'warning'
        if m.group('sev') == 'Error' and code in ('PROCASSWIRE', 'CONTASSREG', 'ASSIGNIN'):
            sev = 'error'
        if sev == 'warning':
            if code not in VERILATOR_KEEP:
                continue
            if f in tb_files and code in VERILATOR_TB_SKIP:
                continue
        msg = m.group('msg').strip()
        msg = re.sub(r'\s*: \.\.\. In instance .*$', '', msg)
        d = {'file': f, 'line': int(m.group('line')), 'col': int(m.group('col')), 'severity': sev,
             'message': msg, 'source': 'verilator', 'code': code}
        diags.append(d)
    return diags


OPENERS = {'begin': 'end', 'case': 'endcase', 'casez': 'endcase', 'casex': 'endcase', 'fork': 'join',
           'module': 'endmodule', 'function': 'endfunction', 'task': 'endtask', 'generate': 'endgenerate'}
CLOSERS = {v: k for k, v in OPENERS.items()}
CLOSERS['endcase'] = 'case'


def structure_check(text, filename):
    """Find unbalanced begin/end, case/endcase... and likely missing semicolons."""
    diags = []
    clean = blank_strings(strip_comments(text))
    lines = clean.split('\n')
    stack = []
    for ln, line in enumerate(lines, 1):
        for m in re.finditer(r'\b(begin|end|case|casez|casex|endcase|fork|join|module|endmodule|function|'
                             r'endfunction|task|endtask|generate|endgenerate)\b', line):
            w = m.group(1)
            if w in OPENERS:
                if w == 'function' or w == 'task':
                    # skip "endfunction" handled; also skip 'disable task' style is rare
                    pass
                stack.append((w, ln, m.start() + 1))
            else:
                want = 'case' if w == 'endcase' else CLOSERS[w]
                if stack and (stack[-1][0] == want or (want == 'case' and stack[-1][0] in ('case', 'casez', 'casex'))):
                    stack.pop()
                else:
                    match_k = None
                    for k in range(len(stack) - 1, -1, -1):
                        if stack[k][0] == want or (want == 'case' and stack[k][0].startswith('case')):
                            match_k = k
                            break
                    if match_k is None:
                        diags.append({'file': filename, 'line': ln, 'col': m.start() + 1, 'severity': 'error',
                                      'message': "'%s' has no matching '%s'" % (w, want), 'source': 'verinest',
                                      'title': 'Unmatched ' + w,
                                      'explain': "There is a '%s' here, but no open '%s' before it." % (w, want),
                                      'fix': "Remove the extra '%s', or add the missing '%s' earlier." % (w, want)})
                    else:
                        for ow, oln, ocol in stack[match_k + 1:]:
                            close = OPENERS[ow]
                            diags.append({'file': filename, 'line': oln, 'col': ocol, 'severity': 'error',
                                          'message': "'%s' is never closed (missing '%s' before line %d)" % (ow, close, ln),
                                          'source': 'verinest', 'title': 'Missing ' + close,
                                          'explain': "This '%s' opens a block, but the '%s' on line %d closes the "
                                                     "outer block first." % (ow, w, ln),
                                          'fix': "Add '%s' to finish this block before line %d." % (close, ln)})
                        del stack[match_k:]
    for w, ln, col in stack:
        close = OPENERS[w]
        diags.append({'file': filename, 'line': ln, 'col': col, 'severity': 'error',
                      'message': "'%s' is never closed (missing '%s')" % (w, close), 'source': 'verinest',
                      'title': 'Missing ' + close,
                      'explain': "This '%s' opens a block but no matching '%s' was found." % (w, close),
                      'fix': "Add '%s' where the block should finish." % close})
    return diags


_NO_SEMI_END = re.compile(r'(;|\bbegin|\bend|\bendcase|\bendmodule|\bendfunction|\bendtask|\bendgenerate|\bjoin'
                          r'|\bfork|[,(\[{:]|\belse|\binitial|^\s*`.*|\)\s*$|^\s*$|\*/)\s*$')


def missing_semicolon_hint(text, line_no):
    """If the line before an error looks like it misses ';', return its line number."""
    clean = blank_strings(strip_comments(text)).split('\n')
    k = line_no - 2
    while k >= 0 and not clean[k].strip():
        k -= 1
    if k < 0:
        return None
    prev = clean[k].rstrip()
    if _NO_SEMI_END.search(prev):
        return None
    if re.match(r'^\s*(if|else|for|while|always|case|casez|casex|repeat|forever|module|function|task)\b', prev):
        return None
    if re.search(r'\b(wire|reg|assign|input|output|integer|parameter|localparam)\b|<=|=|\$\w+|\w+\s*\(', prev):
        return k + 1
    return None


def enrich(diags, files):
    for d in diags:
        if 'explain' in d:
            continue
        info = explain(d['message'], d['source'], d.get('code'))
        if info:
            d.update(info)
        if 'syntax error' in d['message'] and d['file'] in files:
            k = missing_semicolon_hint(files[d['file']], d['line'])
            if k:
                d['title'] = "Missing ';'?"
                d['explain'] = "Line %d looks like it is missing a ';' at the end. " % k + \
                               'The compiler only notices the problem on the next line.'
                d['fix'] = "Add ';' at the end of line %d." % k
                d['related_line'] = k
    return diags
