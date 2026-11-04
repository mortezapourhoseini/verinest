// VeriNest inline suggestion engine.
// Returns ONE grey "ghost" suggestion for the cursor position (accept with Tab / Enter).
// Rule-based and context-aware: block skeletons, module instances, and names declared in the file.
(function () {
  const IND = '    ';
  const KEYWORDS = ('always assign begin case casex casez default defparam else end endcase endfunction endgenerate ' +
    'endmodule endtask for forever function generate genvar if initial inout input integer localparam module negedge ' +
    'output parameter posedge real reg repeat signed task time wait while wire').split(' ');
  const SYSTASKS = ['$display', '$monitor', '$finish', '$dumpfile', '$dumpvars', '$random', '$time', '$stop',
    '$write', '$strobe', '$readmemh', '$readmemb', '$signed', '$unsigned', '$clog2', '$realtime', '$fwrite', '$fopen', '$fclose'];
  const KW_SET = new Set(KEYWORDS);

  function stripComments(t) {
    return t.replace(/\/\*[\s\S]*?\*\//g, m => m.replace(/[^\n]/g, ' ')).replace(/\/\/.*$/gm, '');
  }

  function analyse(text) {
    const clean = stripComments(text);
    const ids = new Map(); // name -> {width, count}
    const declRe = /\b(input|output|inout|wire|reg|integer|parameter|localparam|genvar)\b\s*(?:wire|reg)?\s*(?:signed)?\s*(\[[^\]]+\])?\s*([^;()]*)/g;
    let m;
    while ((m = declRe.exec(clean))) {
      const rng = m[2] || '';
      m[3].split(',').forEach(part => {
        const nm = part.split('=')[0].replace(/\[.*$/, '').trim();
        if (/^[A-Za-z_]\w*$/.test(nm) && !KW_SET.has(nm)) ids.set(nm, { range: rng, count: 0 });
      });
    }
    // module-header style names inside port list after a comma ("input a, b")
    const words = clean.match(/[A-Za-z_]\w*/g) || [];
    const freq = new Map();
    words.forEach(w => freq.set(w, (freq.get(w) || 0) + 1));
    for (const [k, v] of ids) v.count = freq.get(k) || 0;
    const mods = [];
    const modRe = /\bmodule\s+(\w+)/g;
    while ((m = modRe.exec(clean))) mods.push({ name: m[1], index: m.index });
    const clk = [...ids.keys()].find(n => /^(clk|clock|i_clk|clk_i|sys_clk)$/i.test(n));
    const rst = [...ids.keys()].find(n => /^(rst|reset|rst_n|reset_n|rstn|resetn|nrst)$/i.test(n));
    return { ids, freq, mods, clk, rst };
  }

  function currentModule(info, offset) {
    let cur = null;
    for (const m of info.mods) if (m.index <= offset) cur = m.name;
    return cur;
  }

  function widthLiteral(info, name) {
    const v = info.ids.get(name);
    if (!v || !v.range) return { w: 1, lit: n => "1'b" + n };
    const m = v.range.match(/\[\s*(\d+)\s*:\s*(\d+)\s*\]/);
    if (!m) return { w: null, lit: n => String(n) };
    const w = Math.abs(+m[1] - +m[2]) + 1;
    return { w, lit: n => w + "'d" + n };
  }

  function nextLineInfo(model, lineNumber) {
    const total = model.getLineCount();
    for (let l = lineNumber + 1; l <= total; l++) {
      const t = model.getLineContent(l);
      if (t.trim()) return { text: t, indent: t.match(/^\s*/)[0] };
    }
    return null;
  }

  function hasClosingAhead(model, lineNumber, indent, closer) {
    // does a line with the same indentation starting with `closer` follow before a shallower line?
    const total = model.getLineCount();
    for (let l = lineNumber + 1; l <= total; l++) {
      const t = model.getLineContent(l);
      if (!t.trim()) continue;
      const ind = t.match(/^\s*/)[0];
      if (ind.length < indent.length) return false;
      if (ind.length === indent.length) return new RegExp('^\\s*' + closer + '\\b').test(t);
    }
    return false;
  }

  // \u0001 marks where the caret goes after the suggestion is accepted
  const CARET = '\u0001';
  function block(indent, closer, inner) {
    return '\n' + indent + IND + CARET + (inner || '') + '\n' + indent + closer;
  }

  /**
   * ctx = { modules: [{name, ports:[{name,dir}], params:[]}], fileName }
   */
  function suggest(model, position, ctx) {
    const line = model.getLineContent(position.lineNumber);
    const before = line.slice(0, position.column - 1);
    const after = line.slice(position.column - 1);
    const indent = (line.match(/^\s*/) || [''])[0];
    const atEol = after.trim() === '';
    const insideParen = /^\)\s*;?\s*$/.test(after);   // auto-closed ")" right after cursor
    const text = model.getValue();
    const info = analyse(text);
    const offset = model.getOffsetAt(position);
    const thisMod = currentModule(info, offset);
    const clk = info.clk || 'clk';
    const b = before;

    // skip inside comments / strings
    if (/\/\//.test(b) || ((b.match(/"/g) || []).length % 2 === 1)) return null;

    if (atEol) {
      // ----- always -----
      if (/^\s*always\s*$/.test(b))
        return ' @(posedge ' + clk + ') begin' + block(indent, 'end');
      if (/^\s*always\s*@\s*$/.test(b))
        return '(posedge ' + clk + ') begin' + block(indent, 'end');
      if (/^\s*always\s*@\s*\(\s*\*\s*\)\s*$/.test(b) || /^\s*always\s*@\s*\*\s*$/.test(b) ||
          /^\s*always\s*@\s*\((pos|neg)edge\s+\w+(\s+or\s+(pos|neg)edge\s+\w+)*\s*\)\s*$/.test(b))
        return ' begin' + block(indent, 'end');
      if (/^\s*initial\s*$/.test(b)) return ' begin' + block(indent, 'end');
      // ----- begin ... end -----
      if (/\bbegin(\s*:\s*\w+)?\s*$/.test(b) && !hasClosingAhead(model, position.lineNumber, indent, 'end')) {
        const nxt = nextLineInfo(model, position.lineNumber);
        if (!nxt || nxt.indent.length <= indent.length) return block(indent, 'end');
      }
      // ----- case -----
      let m = b.match(/^\s*(case|casez|casex)\s*\(\s*([A-Za-z_]\w*)[^)]*\)\s*$/);
      if (m && !hasClosingAhead(model, position.lineNumber, indent, 'endcase')) {
        const wl = widthLiteral(info, m[2]);
        return '\n' + indent + IND + wl.lit(0) + ': ' + CARET + ';\n' + indent + IND + wl.lit(1) + ': ;\n' +
          indent + IND + 'default: ;\n' + indent + 'endcase';
      }
      // ----- if / else / for / while -----
      if (/^\s*(else\s+)?if\s*\(.*\)\s*$/.test(b) && balanced(b)) return ' begin' + block(indent, 'end');
      if (/^\s*(end\s+)?else\s*$/.test(b)) return ' begin' + block(indent, 'end');
      if (/^\s*(for|while)\s*\(.*\)\s*$/.test(b) && balanced(b)) return ' begin' + block(indent, 'end');
      if (/^\s*repeat\s*\(.*\)\s*$/.test(b) && balanced(b)) return ' begin' + block(indent, 'end');
      if (/^\s*fork\s*$/.test(b)) return block(indent, 'join');
      if (/^\s*generate\s*$/.test(b)) return block(indent, 'endgenerate');
      // ----- module -----
      if (/^\s*module\s*$/.test(b) && ctx.fileName) {
        const base = ctx.fileName.replace(/^.*\//, '').replace(/\.\w+$/, '').replace(/\W/g, '_');
        if (!info.mods.length) return ' ' + base;
      }
      m = b.match(/^\s*module\s+(\w+)\s*$/);
      if (m && !/\bendmodule\b/.test(text.slice(offset))) {
        const sp = /\s$/.test(b) ? '' : ' ';
        if (/^tb/i.test(m[1])) return ';\n\n' + IND + CARET + '\n\nendmodule';
        return sp + '(\n' + IND + 'input  wire       clk,\n' + IND + 'input  wire       rst,\n' + IND +
          'input  wire [7:0] a,\n' + IND + 'output reg  [7:0] y\n);\n\n' + IND + CARET + '\n\nendmodule';
      }
      m = b.match(/^\s*function\s+(?:\[[^\]]+\]\s*)?(\w+)\s*;\s*$/);
      if (m && !hasClosingAhead(model, position.lineNumber, indent, 'endfunction'))
        return block(indent, 'endfunction');
      m = b.match(/^\s*task\s+(\w+)\s*;\s*$/);
      if (m && !hasClosingAhead(model, position.lineNumber, indent, 'endtask')) return block(indent, 'endtask');
      // ----- instance of another module in the project -----
      m = b.match(/^\s*([A-Za-z_]\w*)\s+$/) || b.match(/^\s*([A-Za-z_]\w*)$/);
      if (m && ctx.modules) {
        const mod = ctx.modules.find(x => x.name === m[1] && x.name !== thisMod);
        if (mod && mod.ports && mod.ports.length) {
          const sp = /\s$/.test(b) ? '' : ' ';
          const w = Math.max(...mod.ports.map(p => p.name.length));
          let s = sp;
          if (mod.params && mod.params.length) {
            s += '#(\n' + mod.params.map(p => indent + IND + '.' + p.name + '(' + p.value + ')').join(',\n') + '\n' + indent + ') ';
          }
          s += 'u_' + mod.name + ' (\n' +
            mod.ports.map(p => indent + IND + '.' + p.name.padEnd(w) + '(' + p.name + ')').join(',\n') +
            '\n' + indent + ');';
          return s;
        }
      }
    }

    // ----- inside auto-closed parentheses -----
    if (atEol || insideParen) {
      if (/\$display\s*\(\s*$/.test(b) || /\$monitor\s*\(\s*$/.test(b)) {
        const shown = [...info.ids.keys()].filter(n => !/^(i|j|k)$/.test(n)).slice(0, 3);
        const fmt = shown.map(n => n + '=%0d').join(' ');
        return '"t=%0t ' + fmt + '", $time' + (shown.length ? ', ' + shown.join(', ') : '') + (insideParen ? '' : ');');
      }
      if (/\$dumpfile\s*\(\s*$/.test(b)) return '"' + (thisMod || 'wave') + '.vcd"' + (insideParen ? '' : ');');
      if (/\$dumpvars\s*\(\s*$/.test(b)) return '0, ' + (thisMod || 'tb') + (insideParen ? '' : ');');
      if (/^\s*for\s*\(\s*$/.test(b)) return 'i = 0; i < 8; i = i + 1';
      if (/^\s*always\s*@\s*\(\s*$/.test(b))
        return insideParen ? 'posedge ' + clk : 'posedge ' + clk + ') begin' + block(indent, 'end');
      if (/^\s*repeat\s*\(\s*$/.test(b)) return '10';
    }

    // ----- complete the current word -----
    const wm = b.match(/(\$?[A-Za-z_]\w*)$/);
    if (wm && (atEol || /^[\s)\];,.:=+\-*/&|^<>!?}]/.test(after))) {
      const word = wm[1];
      if (word.length < 2) return null;
      let cands = [];
      if (word[0] === '$') cands = SYSTASKS.filter(s => s.startsWith(word) && s !== word);
      else {
        const declared = [...info.ids.entries()].filter(([n]) => n.startsWith(word) && n !== word)
          .sort((a, b2) => b2[1].count - a[1].count || a[0].length - b2[0].length).map(e => e[0]);
        const mods = (ctx.modules || []).map(x => x.name).filter(n => n.startsWith(word) && n !== word && n !== thisMod);
        const kws = KEYWORDS.filter(k => k.startsWith(word) && k !== word).sort((a, b2) => a.length - b2.length);
        const others = [...info.freq.entries()].filter(([n, c]) => c > 1 && n.startsWith(word) && n !== word && !KW_SET.has(n))
          .sort((a, b2) => b2[1] - a[1]).map(e => e[0]);
        // keywords first only when the line has no code before the word
        const lineStart = b.slice(0, b.length - word.length).trim() === '';
        cands = lineStart ? [...kws, ...declared, ...mods, ...others] : [...declared, ...mods, ...others, ...kws];
        // close-a-block words should match what is open
        if (lineStart && /^end/.test(word)) {
          const want = openCloser(text.slice(0, offset));
          if (want && want.startsWith(word)) cands = [want];
        }
      }
      if (cands.length) return cands[0].slice(word.length);
    }
    return null;
  }

  function balanced(s) {
    let d = 0;
    for (const ch of s) { if (ch === '(') d++; else if (ch === ')') d--; }
    return d === 0;
  }

  // which closing keyword is expected next, based on what is still open before the cursor
  function openCloser(textBefore) {
    const clean = stripComments(textBefore).replace(/"(?:\\.|[^"\\])*"/g, '""');
    const re = /\b(begin|end|case|casez|casex|endcase|module|endmodule|function|endfunction|task|endtask|fork|join|generate|endgenerate)\b/g;
    const pairs = { begin: 'end', case: 'endcase', casez: 'endcase', casex: 'endcase', module: 'endmodule', function: 'endfunction',
      task: 'endtask', fork: 'join', generate: 'endgenerate' };
    const stack = [];
    let m;
    while ((m = re.exec(clean))) {
      const w = m[1];
      if (pairs[w]) stack.push(pairs[w]);
      else if (stack.length && stack[stack.length - 1] === w) stack.pop();
    }
    return stack.length ? stack[stack.length - 1] : null;
  }

  window.VNSuggest = { suggest, analyse, KEYWORDS, SYSTASKS };
})();
