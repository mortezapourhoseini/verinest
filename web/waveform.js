// VeriNest waveform viewer (canvas based)
(function () {
  const ROW_H = 26, RULER_H = 28;
  const UNIT = { s: 1, ms: 1e-3, us: 1e-6, ns: 1e-9, ps: 1e-12, fs: 1e-15 };
  const RADIX_ORDER = ['dec', 'sdec', 'hex', 'bin'];
  const RADIX_LABEL = { dec: 'DEC', sdec: '±DEC', hex: 'HEX', bin: 'BIN' };

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  function fmtValue(v, width, radix, isReal) {
    if (v == null) return '';
    if (isReal) return v;
    if (width === 1 && radix !== 'hex') return v;
    const hasX = /[xz]/.test(v);
    if (radix === 'bin') return v;
    if (hasX) {
      if (/^x+$/.test(v)) return 'x';
      if (/^z+$/.test(v)) return 'z';
      if (radix === 'hex') {
        let out = '';
        const pad = (4 - v.length % 4) % 4;
        const s = '0'.repeat(pad) + v;
        for (let i = 0; i < s.length; i += 4) {
          const nib = s.slice(i, i + 4);
          out += /x/.test(nib) ? 'x' : /z/.test(nib) ? 'z' : parseInt(nib, 2).toString(16);
        }
        return out;
      }
      return 'x';
    }
    const n = BigInt('0b' + v);
    if (radix === 'hex') return n.toString(16).toUpperCase();
    if (radix === 'sdec' && v[0] === '1' && width > 1) return (n - (1n << BigInt(width))).toString();
    return n.toString();
  }

  function parseTimescale(ts) {
    const m = String(ts || '1ns').match(/([\d.]+)\s*([a-z]+)/i);
    if (!m) return 1e-9;
    return parseFloat(m[1]) * (UNIT[m[2].toLowerCase()] || 1e-9);
  }

  function fmtTime(t, tsSec) {
    const s = t * tsSec;
    const a = Math.abs(s);
    let u = 'ps', d = 1e-12;
    if (a >= 1e-3) { u = 'ms'; d = 1e-3; } else if (a >= 1e-6) { u = 'us'; d = 1e-6; } else if (a >= 1e-9) { u = 'ns'; d = 1e-9; }
    let v = s / d;
    v = Math.round(v * 1000) / 1000;
    return v + ' ' + u;
  }

  function lastIndexAtOrBefore(ch, t) {
    let lo = 0, hi = ch.length - 1, ans = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (ch[mid][0] <= t) { ans = mid; lo = mid + 1; } else hi = mid - 1;
    }
    return ans;
  }

  class WaveView {
    constructor(root) {
      this.root = root;
      this.data = null;
      this.sigs = [];
      this.sel = -1;
      this.t0 = 0; this.scale = 1;
      this.cursor = null; this.marker = null;
      this.hoverT = null;
      this.build();
    }

    build() {
      this.root.innerHTML = `
        <div class="w-toolbar">
          <button class="btn" data-a="pick" title="Show / hide the signal list">${vnIcon('list')}Signals</button>
          <div class="sep"></div>
          <button class="icon-btn" data-a="zin" title="Zoom in (+ or Ctrl+wheel)">${vnIcon('zin')}</button>
          <button class="icon-btn" data-a="zout" title="Zoom out (-)">${vnIcon('zout')}</button>
          <button class="icon-btn" data-a="fit" title="Zoom to fit (F)">${vnIcon('fit')}</button>
          <div class="sep"></div>
          <button class="icon-btn" data-a="prev" title="Jump to previous edge of the selected signal (←)">${vnIcon('prev')}</button>
          <button class="icon-btn" data-a="next" title="Jump to next edge of the selected signal (→)">${vnIcon('next')}</button>
          <select data-a="radix" title="Number format of the selected signal">
            <option value="dec">Decimal</option><option value="sdec">Signed decimal</option>
            <option value="hex">Hex</option><option value="bin">Binary</option>
          </select>
          <div class="w-info"><span>Cursor <b data-i="cur">—</b></span><span class="mk">Marker <span data-i="mk">—</span></span><span>Δ <span data-i="dt">—</span></span></div>
          <div class="spacer"></div>
          <span class="w-info" data-i="hover"></span>
        </div>
        <div class="w-body">
          <div class="w-picker">
            <input type="text" placeholder="Filter signals…" spellcheck="false">
            <div class="w-ptree"></div>
            <div class="w-picker-actions">
              <button class="btn" data-a="addall">Add all</button>
              <button class="btn" data-a="clear">Remove all</button>
            </div>
          </div>
          <div class="w-scroll" tabindex="0">
            <div class="w-names"><div class="w-names-head">SIGNAL<span class="spacer"></span>VALUE</div><div class="w-rows"></div></div>
            <div class="w-canvas-wrap"><canvas></canvas></div>
          </div>
          <div class="w-empty">${vnIcon('wave')}<div>Run a simulation (<kbd>F5</kbd>) to see waveforms here.<br>
            <span style="font-size:12px">Tip: Ctrl+wheel zooms, drag to pan, click to place the cursor, Shift+click places a marker.</span></div></div>
        </div>`;
      const q = s => this.root.querySelector(s);
      this.el = {
        picker: q('.w-picker'), filter: q('.w-picker input'), ptree: q('.w-ptree'), scroll: q('.w-scroll'),
        rows: q('.w-rows'), wrap: q('.w-canvas-wrap'), canvas: q('canvas'), empty: q('.w-empty'),
        radix: q('select[data-a=radix]'), cur: q('[data-i=cur]'), mk: q('[data-i=mk]'), dt: q('[data-i=dt]'), hover: q('[data-i=hover]'),
      };
      this.ctx = this.el.canvas.getContext('2d');
      this.root.querySelectorAll('[data-a]').forEach(b => {
        if (b.tagName === 'SELECT') b.onchange = () => this.setRadix(b.value);
        else b.onclick = () => this.action(b.dataset.a);
      });
      this.el.filter.oninput = () => this.renderPicker();
      this.el.scroll.addEventListener('scroll', () => this.draw());
      new ResizeObserver(() => this.resize()).observe(this.el.scroll);
      const c = this.el.canvas;
      c.addEventListener('mousedown', e => this.onDown(e));
      window.addEventListener('mousemove', e => this.onMove(e));
      window.addEventListener('mouseup', e => this.onUp(e));
      c.addEventListener('mousemove', e => { this.hoverT = this.xToT(e.offsetX); this.updateInfo(); });
      c.addEventListener('mouseleave', () => { this.hoverT = null; this.updateInfo(); });
      this.el.scroll.addEventListener('wheel', e => this.onWheel(e), { passive: false });
      this.el.scroll.addEventListener('keydown', e => this.onKey(e));
      this.updateEmpty();
    }

    // ---------- data ----------
    load(data) {
      const prev = new Map(this.sigs.map(s => [s.path, s.radix]));
      const hadData = !!this.data;
      this.data = data;
      this.tsSec = parseTimescale(data.timescale);
      const byPath = new Map();
      Object.values(data.signals).forEach(s => byPath.set(s.path, s));
      const all = this.allSignals();
      let keep = this.sigs.map(s => byPath.get(s.path) ? this.mkSig(byPath.get(s.path), all) : null).filter(Boolean);
      if (!keep.length) {
        // default: every signal of the first (top) scope
        const top = data.scopes[0];
        const list = top ? top.signals : all.slice(0, 30);
        keep = list.slice(0, 48).map(s => this.mkSig(s, all));
      }
      keep.forEach(s => { if (prev.has(s.path)) s.radix = prev.get(s.path); });
      this.sigs = keep;
      this.sel = Math.min(Math.max(this.sel, 0), this.sigs.length - 1);
      if (!hadData || this.cursor == null || this.cursor > data.end) {
        this.cursor = null; this.marker = null;
        if (this.el.wrap.clientWidth > 0) this.fit(); else this.needFit = true;
      }
      this.renderPicker();
      this.renderRows();
      this.updateEmpty();
      this.resize();
    }

    mkSig(s, all) {
      const top = this.data.scopes[0] ? this.data.scopes[0].name + '.' : '';
      const short = s.path.startsWith(top) ? s.path.slice(top.length) : s.path;
      return { id: s.id, path: s.path, name: short, width: s.width, real: !!this.data.signals[s.id].real,
        radix: s.width > 1 ? 'dec' : 'bin' };
    }

    allSignals() {
      const out = [];
      const walk = n => { n.signals.forEach(s => out.push(s)); n.children.forEach(walk); };
      (this.data ? this.data.scopes : []).forEach(walk);
      return out;
    }

    updateEmpty() {
      const has = this.data && this.sigs.length;
      this.el.empty.style.display = this.data ? 'none' : 'grid';
      this.el.scroll.style.visibility = this.data ? 'visible' : 'hidden';
      if (this.data && !has) this.el.picker.classList.add('open');
    }

    // ---------- picker ----------
    renderPicker() {
      if (!this.data) { this.el.ptree.innerHTML = ''; return; }
      const f = this.el.filter.value.trim().toLowerCase();
      const added = new Set(this.sigs.map(s => s.path));
      let html = '';
      const walk = (n, depth) => {
        const sigs = n.signals.filter(s => !f || s.path.toLowerCase().includes(f));
        let inner = '';
        sigs.forEach(s => {
          inner += `<div class="w-sig ${added.has(s.path) ? 'added' : ''}" data-path="${esc(s.path)}" style="padding-left:${22 + depth * 12}px">
            <span>${esc(s.name)}</span>${s.width > 1 ? `<span class="w">[${s.width - 1}:0]</span>` : ''}</div>`;
        });
        const kids = n.children.map(c => walk(c, depth + 1)).join('');
        if (!inner && !kids) return '';
        return `<div class="w-scope" data-scope="${esc(n.name)}" style="padding-left:${8 + depth * 12}px">${vnIcon('down')}${esc(n.name)}</div>` + inner + kids;
      };
      this.data.scopes.forEach(s => { html += walk(s, 0); });
      this.el.ptree.innerHTML = html || '<div class="empty-hint">No signals</div>';
      this.el.ptree.querySelectorAll('.w-sig').forEach(d => d.onclick = () => this.toggleSignal(d.dataset.path));
    }

    toggleSignal(path) {
      const i = this.sigs.findIndex(s => s.path === path);
      if (i >= 0) this.sigs.splice(i, 1);
      else {
        const s = this.allSignals().find(x => x.path === path);
        if (s) { this.sigs.push(this.mkSig(s)); this.sel = this.sigs.length - 1; }
      }
      this.renderPicker(); this.renderRows(); this.resize();
    }

    // ---------- names column ----------
    renderRows() {
      this.el.rows.innerHTML = this.sigs.map((s, i) => `
        <div class="w-row ${i === this.sel ? 'sel' : ''}" data-i="${i}" draggable="true" title="${esc(s.path)}${s.width > 1 ? ' [' + (s.width - 1) + ':0]' : ''}">
          <span class="nm">${this.nameHtml(s)}</span>
          <span class="val"></span>
          ${s.width > 1 ? `<span class="rdx" title="Click to change number format">${RADIX_LABEL[s.radix]}</span>` : ''}
        </div>`).join('');
      this.el.rows.querySelectorAll('.w-row').forEach(r => {
        const i = +r.dataset.i;
        r.onclick = e => {
          if (e.target.classList.contains('rdx')) {
            const s = this.sigs[i];
            s.radix = RADIX_ORDER[(RADIX_ORDER.indexOf(s.radix) + 1) % RADIX_ORDER.length];
          }
          this.select(i);
        };
        r.ondragstart = e => { this.dragFrom = i; e.dataTransfer.effectAllowed = 'move'; };
        r.ondragover = e => { e.preventDefault(); r.classList.add('dragover'); };
        r.ondragleave = () => r.classList.remove('dragover');
        r.ondrop = e => {
          e.preventDefault(); r.classList.remove('dragover');
          if (this.dragFrom == null || this.dragFrom === i) return;
          const [s] = this.sigs.splice(this.dragFrom, 1);
          this.sigs.splice(i, 0, s); this.sel = i; this.dragFrom = null;
          this.renderRows(); this.draw();
        };
      });
      this.updateValues();
    }

    nameHtml(s) {
      const k = s.name.lastIndexOf('.');
      return k < 0 ? esc(s.name) : `<span class="scope">${esc(s.name.slice(0, k + 1))}</span>${esc(s.name.slice(k + 1))}`;
    }

    select(i) {
      this.sel = i;
      const s = this.sigs[i];
      if (s) this.el.radix.value = s.radix;
      this.renderRows(); this.draw();
      this.el.scroll.focus({ preventScroll: true });
    }

    setRadix(r) {
      const s = this.sigs[this.sel];
      if (s) { s.radix = r; this.renderRows(); this.draw(); }
    }

    valueAt(s, t) {
      const ch = this.data.changes[s.id];
      const k = lastIndexAtOrBefore(ch, t);
      return k < 0 ? null : ch[k][1];
    }

    updateValues() {
      const t = this.cursor;
      this.el.rows.querySelectorAll('.w-row').forEach(r => {
        const s = this.sigs[+r.dataset.i];
        const v = (t == null || !s) ? '' : fmtValue(this.valueAt(s, t), s.width, s.radix, s.real);
        r.querySelector('.val').textContent = v;
      });
      this.updateInfo();
    }

    updateInfo() {
      const f = t => t == null ? '—' : fmtTime(t, this.tsSec);
      this.el.cur.textContent = f(this.cursor);
      this.el.mk.textContent = f(this.marker);
      this.el.dt.textContent = (this.cursor != null && this.marker != null) ? fmtTime(Math.abs(this.cursor - this.marker), this.tsSec) : '—';
      this.el.hover.textContent = this.hoverT != null && this.data ? fmtTime(Math.max(0, Math.round(this.hoverT)), this.tsSec) : '';
    }

    // ---------- view math ----------
    viewW() { return this.el.canvas.width / (window.devicePixelRatio || 1); }
    xToT(x) { return this.t0 + x / this.scale; }
    tToX(t) { return (t - this.t0) * this.scale; }

    fit() {
      if (!this.data) return;
      const w = Math.max(100, this.el.wrap.clientWidth || 600);
      const end = Math.max(1, this.data.end);
      this.scale = (w - 30) / end;
      this.t0 = 0;
    }

    zoom(f, atX) {
      const w = this.viewW();
      const x = atX == null ? (this.cursor != null && this.tToX(this.cursor) >= 0 && this.tToX(this.cursor) <= w ? this.tToX(this.cursor) : w / 2) : atX;
      const t = this.xToT(x);
      this.scale = Math.min(1e6, Math.max(1e-9, this.scale * f));
      this.t0 = t - x / this.scale;
      this.clampT0();
      this.draw();
    }

    clampT0() {
      if (!this.data) return;
      const w = this.viewW();
      const maxT0 = Math.max(0, this.data.end - (w * 0.5) / this.scale);
      this.t0 = Math.min(Math.max(this.t0, -20 / this.scale), maxT0);
    }

    action(a) {
      if (a === 'pick') this.el.picker.classList.toggle('open');
      else if (a === 'zin') this.zoom(1.6);
      else if (a === 'zout') this.zoom(1 / 1.6);
      else if (a === 'fit') { this.fit(); this.draw(); }
      else if (a === 'prev' || a === 'next') this.jumpEdge(a === 'next' ? 1 : -1);
      else if (a === 'addall') {
        const all = this.allSignals();
        const have = new Set(this.sigs.map(s => s.path));
        all.forEach(s => { if (!have.has(s.path)) this.sigs.push(this.mkSig(s)); });
        this.renderPicker(); this.renderRows(); this.resize();
      } else if (a === 'clear') { this.sigs = []; this.sel = -1; this.renderPicker(); this.renderRows(); this.resize(); }
      setTimeout(() => this.resize(), 0);
    }

    jumpEdge(dir) {
      const s = this.sigs[this.sel] || this.sigs[0];
      if (!s || !this.data) return;
      const ch = this.data.changes[s.id];
      const t = this.cursor == null ? (dir > 0 ? -1 : Infinity) : this.cursor;
      let target = null;
      if (dir > 0) { const k = lastIndexAtOrBefore(ch, t); if (k + 1 < ch.length) target = ch[k + 1][0]; }
      else { let k = lastIndexAtOrBefore(ch, t); if (k >= 0 && ch[k][0] === t) k--; if (k >= 0) target = ch[k][0]; }
      if (target == null) return;
      this.cursor = target;
      const x = this.tToX(target), w = this.viewW();
      if (x < 20 || x > w - 20) { this.t0 = target - w / 2 / this.scale; this.clampT0(); }
      this.updateValues(); this.draw();
    }

    // ---------- events ----------
    onDown(e) {
      if (e.button !== 0) return;
      this.drag = { x: e.clientX, y: e.offsetY, t0: this.t0, moved: false, shift: e.shiftKey, offX: e.offsetX };
      this.el.scroll.focus({ preventScroll: true });
    }
    onMove(e) {
      if (!this.drag) return;
      const dx = e.clientX - this.drag.x;
      if (Math.abs(dx) > 3) this.drag.moved = true;
      if (this.drag.moved) { this.t0 = this.drag.t0 - dx / this.scale; this.clampT0(); this.draw(); }
    }
    onUp() {
      const d = this.drag;
      this.drag = null;
      if (!d || d.moved || !this.data) return;
      let t = Math.max(0, this.xToT(d.offX));
      // snap to nearest edge of any visible signal within 6px
      let best = null, bestDx = 6;
      for (const s of this.sigs) {
        const ch = this.data.changes[s.id];
        const k = lastIndexAtOrBefore(ch, t);
        [k, k + 1].forEach(j => {
          if (j >= 0 && j < ch.length) {
            const dx = Math.abs(this.tToX(ch[j][0]) - d.offX);
            if (dx < bestDx) { bestDx = dx; best = ch[j][0]; }
          }
        });
      }
      if (best != null) t = best; else t = Math.round(t);
      if (d.shift) this.marker = t; else this.cursor = t;
      const row = Math.floor((d.y + this.el.scroll.scrollTop - RULER_H) / ROW_H);
      if (d.y > RULER_H && row >= 0 && row < this.sigs.length) { this.sel = row; this.el.radix.value = this.sigs[row].radix; this.renderRows(); }
      this.updateValues(); this.draw();
    }
    onWheel(e) {
      if (!this.data) return;
      const rect = this.el.canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        if (x >= 0) this.zoom(e.deltaY < 0 ? 1.25 : 0.8, x);
      } else if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        e.preventDefault();
        const d = (e.shiftKey ? e.deltaY : e.deltaX);
        this.t0 += d / this.scale; this.clampT0(); this.draw();
      }
    }
    onKey(e) {
      const k = e.key;
      if (k === '+' || k === '=') this.zoom(1.6);
      else if (k === '-') this.zoom(1 / 1.6);
      else if (k === 'f' || k === 'F') { this.fit(); this.draw(); }
      else if (k === 'ArrowRight') this.jumpEdge(1);
      else if (k === 'ArrowLeft') this.jumpEdge(-1);
      else if (k === 'ArrowDown') { if (this.sel < this.sigs.length - 1) this.select(this.sel + 1); }
      else if (k === 'ArrowUp') { if (this.sel > 0) this.select(this.sel - 1); }
      else if (k === 'Delete' || k === 'Backspace') {
        if (this.sel >= 0) { this.sigs.splice(this.sel, 1); this.sel = Math.min(this.sel, this.sigs.length - 1); this.renderPicker(); this.renderRows(); this.resize(); }
      } else return;
      e.preventDefault();
    }

    // ---------- drawing ----------
    resize() {
      const dpr = window.devicePixelRatio || 1;
      if (this.needFit && this.el.wrap.clientWidth > 0) { this.needFit = false; this.fit(); }
      const w = Math.max(50, this.el.wrap.clientWidth);
      const h = Math.max(50, this.el.scroll.clientHeight);
      const total = RULER_H + this.sigs.length * ROW_H + 8;
      this.el.wrap.style.height = Math.max(total, h) + 'px';
      this.el.canvas.width = Math.floor(w * dpr);
      this.el.canvas.height = Math.floor(h * dpr);
      this.el.canvas.style.width = w + 'px';
      this.el.canvas.style.height = h + 'px';
      this.draw();
    }

    draw() {
      const ctx = this.ctx, dpr = window.devicePixelRatio || 1;
      const W = this.el.canvas.width / dpr, H = this.el.canvas.height / dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const C = {
        bg: css('--w-bg'), grid: css('--w-grid'), ruler: css('--w-ruler'), bit: css('--w-bit'), bus: css('--w-bus'),
        busFill: css('--w-bus-fill'), x: css('--w-x'), z: css('--w-z'), cur: css('--w-cursor'), mk: css('--w-marker'),
        text: css('--w-text'), dim: css('--fg-3'), line: css('--line'), sel: css('--w-row-sel'),
      };
      ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
      if (!this.data) return;
      const st = this.el.scroll.scrollTop;
      // tick spacing
      const target = 110 / this.scale;
      const p = Math.pow(10, Math.floor(Math.log10(Math.max(target, 1e-12))));
      let step = p;
      for (const m of [1, 2, 5, 10]) { if (p * m >= target) { step = p * m; break; } }
      step = Math.max(step, 1);
      const tStart = Math.floor(this.xToT(0) / step) * step;
      // grid
      ctx.strokeStyle = C.grid; ctx.lineWidth = 1;
      ctx.beginPath();
      for (let t = tStart; this.tToX(t) < W; t += step) {
        const x = Math.round(this.tToX(t)) + 0.5;
        ctx.moveTo(x, RULER_H); ctx.lineTo(x, H);
      }
      ctx.stroke();
      // rows
      ctx.font = '11.5px "JetBrains Mono", "DejaVu Sans Mono", monospace';
      ctx.textBaseline = 'middle';
      const tL = this.xToT(-5), tR = this.xToT(W + 5);
      this.sigs.forEach((s, i) => {
        const y0 = RULER_H + i * ROW_H - st;
        if (y0 + ROW_H < RULER_H || y0 > H) return;
        if (i === this.sel) { ctx.fillStyle = C.sel; ctx.fillRect(0, y0, W, ROW_H); }
        ctx.strokeStyle = C.grid; ctx.beginPath(); ctx.moveTo(0, y0 + ROW_H - 0.5); ctx.lineTo(W, y0 + ROW_H - 0.5); ctx.stroke();
        this.drawSignal(ctx, s, y0, tL, tR, W, C);
      });
      // end-of-sim shade
      const xe = this.tToX(this.data.end);
      if (xe < W) { ctx.fillStyle = 'rgba(128,128,128,0.06)'; ctx.fillRect(Math.max(0, xe), RULER_H, W, H); }
      // ruler
      ctx.fillStyle = C.ruler; ctx.fillRect(0, 0, W, RULER_H);
      ctx.strokeStyle = C.line; ctx.beginPath(); ctx.moveTo(0, RULER_H - 0.5); ctx.lineTo(W, RULER_H - 0.5); ctx.stroke();
      ctx.fillStyle = C.dim; ctx.strokeStyle = C.dim; ctx.textBaseline = 'middle';
      ctx.font = '10.5px "JetBrains Mono", "DejaVu Sans Mono", monospace';
      ctx.beginPath();
      for (let t = tStart; this.tToX(t) < W; t += step) {
        const x = Math.round(this.tToX(t)) + 0.5;
        if (x < -40) continue;
        ctx.moveTo(x, RULER_H - 7); ctx.lineTo(x, RULER_H);
        if (t >= 0) ctx.fillText(fmtTime(t, this.tsSec), x + 4, 11);
        const minor = step / 5;
        for (let k = 1; k < 5; k++) { const xm = Math.round(this.tToX(t + k * minor)) + 0.5; ctx.moveTo(xm, RULER_H - 3); ctx.lineTo(xm, RULER_H); }
      }
      ctx.stroke();
      // marker & cursor
      const vline = (t, color, dash, label) => {
        const x = Math.round(this.tToX(t)) + 0.5;
        if (x < 0 || x > W) return;
        ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.setLineDash(dash);
        ctx.beginPath(); ctx.moveTo(x, RULER_H); ctx.lineTo(x, H); ctx.stroke(); ctx.restore();
        ctx.font = 'bold 10.5px "JetBrains Mono", "DejaVu Sans Mono", monospace';
        const tw = ctx.measureText(label).width + 10;
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x - tw / 2, RULER_H - 17, tw, 15, 4) : ctx.rect(x - tw / 2, RULER_H - 17, tw, 15); ctx.fill();
        ctx.fillStyle = C.bg; ctx.textAlign = 'center'; ctx.fillText(label, x, RULER_H - 9); ctx.textAlign = 'left';
      };
      if (this.marker != null) vline(this.marker, C.mk, [4, 3], fmtTime(this.marker, this.tsSec));
      if (this.cursor != null) vline(this.cursor, C.cur, [], fmtTime(this.cursor, this.tsSec));
    }

    drawSignal(ctx, s, y0, tL, tR, W, C) {
      const ch = this.data.changes[s.id];
      if (!ch || !ch.length) return;
      const hi = y0 + 5, lo = y0 + ROW_H - 6, mid = (hi + lo) / 2;
      let k = Math.max(0, lastIndexAtOrBefore(ch, tL));
      const end = this.data.end;
      const isBit = s.width === 1 && !s.real;
      if (isBit) {
        ctx.lineWidth = 1.5;
        let prevY = null;
        for (; k < ch.length; k++) {
          const t = ch[k][0];
          if (t > tR) break;
          const tn = k + 1 < ch.length ? ch[k + 1][0] : end;
          const x1 = Math.max(-2, this.tToX(t)), x2 = Math.min(W + 2, this.tToX(tn));
          const v = ch[k][1];
          if (v === 'x') {
            ctx.fillStyle = C.x + '33'; ctx.fillRect(x1, hi, x2 - x1, lo - hi);
            ctx.strokeStyle = C.x; ctx.beginPath(); ctx.moveTo(x1, hi); ctx.lineTo(x2, hi); ctx.moveTo(x1, lo); ctx.lineTo(x2, lo); ctx.stroke();
            prevY = null; continue;
          }
          if (v === 'z') {
            ctx.strokeStyle = C.z; ctx.beginPath(); ctx.moveTo(x1, mid); ctx.lineTo(x2, mid); ctx.stroke();
            prevY = mid; continue;
          }
          const y = v === '1' ? hi : lo;
          ctx.strokeStyle = C.bit;
          ctx.beginPath();
          if (prevY != null && prevY !== y) { ctx.moveTo(x1, prevY); ctx.lineTo(x1, y); }
          ctx.moveTo(x1, y); ctx.lineTo(x2, y); ctx.stroke();
          if (v === '1') { ctx.fillStyle = C.bit + '1a'; ctx.fillRect(x1, hi, x2 - x1, lo - hi); }
          prevY = y;
        }
        return;
      }
      ctx.lineWidth = 1.2;
      for (; k < ch.length; k++) {
        const t = ch[k][0];
        if (t > tR) break;
        const tn = k + 1 < ch.length ? ch[k + 1][0] : end;
        const xa = this.tToX(t), xb = this.tToX(tn);
        if (xb < -5) continue;
        const v = ch[k][1];
        const isX = !s.real && /x/.test(v), isZ = !s.real && /^z+$/.test(v);
        const col = isX ? C.x : isZ ? C.z : C.bus;
        const sl = Math.min(3, (xb - xa) / 2);
        ctx.beginPath();
        ctx.moveTo(xa, mid); ctx.lineTo(xa + sl, hi); ctx.lineTo(xb - sl, hi); ctx.lineTo(xb, mid);
        ctx.lineTo(xb - sl, lo); ctx.lineTo(xa + sl, lo); ctx.closePath();
        ctx.fillStyle = isX ? C.x + '26' : isZ ? C.z + '22' : C.busFill; ctx.fill();
        ctx.strokeStyle = col; ctx.stroke();
        const txt = fmtValue(v, s.width, s.radix, s.real);
        const vx1 = Math.max(xa + sl + 3, 2), vx2 = Math.min(xb - sl - 3, W - 2);
        const room = vx2 - vx1;
        if (room > 8) {
          ctx.fillStyle = isX ? C.x : C.text;
          let shown = txt;
          if (ctx.measureText(shown).width > room) {
            while (shown.length > 1 && ctx.measureText(shown + '…').width > room) shown = shown.slice(0, -1);
            shown = shown.length > 1 ? shown + '…' : '';
          }
          if (shown) {
            const tw = ctx.measureText(shown).width;
            const cx = Math.max(vx1, Math.min((Math.max(xa, 0) + Math.min(xb, W)) / 2 - tw / 2, vx2 - tw));
            ctx.fillText(shown, cx, mid + 0.5);
          }
        }
      }
    }
  }

  window.VNWave = { WaveView, fmtValue, fmtTime };
})();
