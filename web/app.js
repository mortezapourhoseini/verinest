// VeriNest main UI controller
(function () {
  'use strict';
  vnHydrateIcons();

  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const S = {
    projects: [], examples: [], tools: {},
    project: null,              // active project name
    tabs: [],                   // {key, project, path, model, dirty, view}
    active: null,               // tab key
    openProjects: new Set(),
    diagnostics: [],            // last lint/compile diagnostics for the active project
    modules: [],
    selectedProblem: null,
    lintTimer: null, lintSeq: 0,
    theme: document.documentElement.dataset.theme || 'dark',
    topChoice: {},              // project -> chosen top ('' = auto)
  };
  let editor = null, monaco = null, wave = null, decorations = [];
  let pendingCaret = null;   // where to put the caret after a multi-line suggestion is accepted

  // ---------------------------------------------------------------- API
  async function api(path, body, query) {
    let url = path + (query ? '?' + new URLSearchParams(query) : '');
    const opt = { method: body ? 'POST' : 'GET', headers: { 'X-Token': window.VN_TOKEN } };
    if (body) { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; }
    const r = await fetch(url, opt);
    const j = await r.json().catch(() => ({ error: 'Bad response' }));
    if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
    return j;
  }

  function toast(msg, err) {
    const t = $('#toast');
    t.textContent = msg; t.className = 'show' + (err ? ' err' : '');
    clearTimeout(t._h); t._h = setTimeout(() => t.className = '', 2600);
  }

  // ---------------------------------------------------------------- modal
  function modal({ title, body = '', input = null, ok = 'OK', danger = false, cancel = true }) {
    return new Promise(res => {
      $('#modalTitle').textContent = title;
      $('#modalBody').innerHTML = body;
      const inp = $('#modalInput');
      inp.classList.toggle('hidden', input === null);
      inp.value = input || '';
      const okb = $('#modalOk');
      okb.textContent = ok; okb.className = 'btn ' + (danger ? 'danger' : 'primary');
      $('#modalCancel').style.display = cancel ? '' : 'none';
      $('#modal').classList.remove('hidden');
      setTimeout(() => { if (input !== null) { inp.focus(); inp.select(); } else okb.focus(); }, 30);
      const done = v => { $('#modal').classList.add('hidden'); okb.onclick = null; $('#modalCancel').onclick = null; inp.onkeydown = null; res(v); };
      okb.onclick = () => done(input !== null ? inp.value.trim() : true);
      $('#modalCancel').onclick = () => done(null);
      inp.onkeydown = e => { if (e.key === 'Enter') okb.click(); if (e.key === 'Escape') done(null); };
      $('#modal').onkeydown = e => { if (e.key === 'Escape') done(null); };
    });
  }

  // ---------------------------------------------------------------- theme
  function applyTheme(t) {
    S.theme = t;
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem('vn-theme', t); } catch (e) { /* ignore */ }
    $('#btnTheme').innerHTML = vnIcon(t === 'dark' ? 'sun' : 'moon');
    if (monaco) monaco.editor.setTheme(t === 'dark' ? 'verinest-dark' : 'verinest-light');
    if (wave) wave.draw();
  }

  function defineThemes() {
    monaco.editor.defineTheme('verinest-dark', {
      base: 'vs-dark', inherit: true,
      rules: [
        { token: 'keyword', foreground: 'c792ea' },
        { token: 'type', foreground: '5ab0ff' },
        { token: 'comment', foreground: '6a7383', fontStyle: 'italic' },
        { token: 'number', foreground: 'f5a524' },
        { token: 'string', foreground: '3ddc97' },
        { token: 'identifier', foreground: 'd7dae0' },
        { token: 'variable.predefined', foreground: '4fd1c5' },
        { token: 'keyword.directive', foreground: 'ff8f6b' },
        { token: 'delimiter', foreground: '8b93a1' },
        { token: 'operator', foreground: '89ddff' },
      ],
      colors: {
        'editor.background': '#16181d', 'editor.foreground': '#d7dae0',
        'editorLineNumber.foreground': '#4b5260', 'editorLineNumber.activeForeground': '#f5a524',
        'editor.lineHighlightBackground': '#1d2027', 'editor.selectionBackground': '#2d3f5c',
        'editorCursor.foreground': '#f5a524', 'editorIndentGuide.background': '#252932',
        'editorIndentGuide.activeBackground': '#3a404b', 'editorGutter.background': '#16181d',
        'editorGhostText.foreground': '#7c8494', 'editorWidget.background': '#1c1f26',
        'editorHoverWidget.background': '#1c1f26', 'editorHoverWidget.border': '#3a404b',
        'minimap.background': '#16181d', 'scrollbarSlider.background': '#2b303980',
      }
    });
    monaco.editor.defineTheme('verinest-light', {
      base: 'vs', inherit: true,
      rules: [
        { token: 'keyword', foreground: '8e44ad' },
        { token: 'type', foreground: '1f6fd1' },
        { token: 'comment', foreground: '9a9a90', fontStyle: 'italic' },
        { token: 'number', foreground: 'c25e00' },
        { token: 'string', foreground: '148a55' },
        { token: 'variable.predefined', foreground: '0b7f8a' },
        { token: 'keyword.directive', foreground: 'c2410c' },
        { token: 'operator', foreground: '0369a1' },
      ],
      colors: {
        'editor.background': '#ffffff', 'editor.lineHighlightBackground': '#faf8f4',
        'editorLineNumber.foreground': '#b9b4aa', 'editorLineNumber.activeForeground': '#d9730d',
        'editorCursor.foreground': '#d9730d', 'editorGhostText.foreground': '#a19c92',
        'editorIndentGuide.background': '#efece6',
      }
    });
  }

  // ---------------------------------------------------------------- monaco
  function initMonaco() {
    return new Promise(resolve => {
      require.config({ paths: { vs: 'vendor/monaco/vs' } });
      require(['vs/editor/editor.main'], () => {
        monaco = window.monaco;
        defineThemes();
        editor = monaco.editor.create($('#editor'), {
          theme: S.theme === 'dark' ? 'verinest-dark' : 'verinest-light',
          fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", "DejaVu Sans Mono", "Ubuntu Mono", monospace',
          fontSize: 14, lineHeight: 21, tabSize: 4, insertSpaces: true, automaticLayout: true,
          minimap: { enabled: true, renderCharacters: false, scale: 1 }, scrollBeyondLastLine: false,
          smoothScrolling: true, cursorBlinking: 'smooth', cursorSmoothCaretAnimation: 'on',
          renderWhitespace: 'selection', bracketPairColorization: { enabled: true }, guides: { bracketPairs: true, indentation: true },
          // one inline suggestion instead of a popup list
          quickSuggestions: false, suggestOnTriggerCharacters: false, wordBasedSuggestions: false,
          inlineSuggest: { enabled: true, showToolbar: 'never' }, tabCompletion: 'off', acceptSuggestionOnEnter: 'off',
          parameterHints: { enabled: false }, padding: { top: 10 }, fixedOverflowWidgets: true,
          stickyScroll: { enabled: false }, renderLineHighlight: 'all', 'semanticHighlighting.enabled': false,
        });
        registerProviders();
        // after accepting a block suggestion, move the caret inside the block (like a snippet)
        editor.onDidChangeModelContent(e => {
          const pc = pendingCaret;
          if (!pc || pc.caret == null || editor.getModel() !== pc.model) return;
          const ch = e.changes.find(c => c.text === pc.text && c.rangeOffset === pc.offset);
          if (!ch) return;
          pendingCaret = null;
          setTimeout(() => {
            editor.setPosition(pc.model.getPositionAt(pc.offset + pc.caret));
            editor.focus();
          }, 0);
        });
        editor.onDidChangeCursorPosition(e => {
          $('#sbPos').textContent = 'Ln ' + e.position.lineNumber + ', Col ' + e.position.column;
        });
        // Enter accepts the ghost suggestion (Tab works by default)
        editor.addCommand(monaco.KeyCode.Enter, () => editor.trigger('vn', 'editor.action.inlineSuggest.commit', {}), 'inlineSuggestionVisible');
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, saveActive);
        editor.addCommand(monaco.KeyCode.F5, run);
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyB, run);
        editor.addCommand(monaco.KeyMod.Shift | monaco.KeyMod.Alt | monaco.KeyCode.KeyF, formatActive);
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyL, () => lintNow(true));
        editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyJ, togglePanel);
        resolve();
      });
    });
  }

  function registerProviders() {
    monaco.languages.registerInlineCompletionsProvider('verilog', {
      provideInlineCompletions(model, position) {
        const tab = S.tabs.find(t => t.model === model);
        let text = VNSuggest.suggest(model, position, { modules: S.modules, fileName: tab ? tab.path : '' });
        if (!text) { pendingCaret = null; return { items: [] }; }
        const k = text.indexOf('\u0001');
        text = text.replace('\u0001', '');
        pendingCaret = { model, offset: model.getOffsetAt(position), text, caret: k < 0 ? null : k };
        return { items: [{ insertText: text, range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column) }] };
      },
      freeInlineCompletions() { },
      handleItemDidShow() { },
    });
    monaco.languages.registerDocumentFormattingEditProvider('verilog', {
      async provideDocumentFormattingEdits(model) {
        const r = await api('/api/format', { content: model.getValue() });
        return [{ range: model.getFullModelRange(), text: r.content }];
      }
    });
    // hover on a module name shows its ports
    monaco.languages.registerHoverProvider('verilog', {
      provideHover(model, pos) {
        const w = model.getWordAtPosition(pos);
        if (!w) return null;
        const m = S.modules.find(x => x.name === w.word);
        if (!m) return null;
        const ports = m.ports.map(p => '`' + p.dir + ' ' + (p.range ? p.range + ' ' : '') + p.name + '`').join('  \n');
        return { contents: [{ value: '**module ' + m.name + '**  — ' + m.file + ':' + m.line }, { value: ports || '_no ports_' }] };
      }
    });
    // F12 / right-click: go to the definition of the module under the cursor
    editor.addAction({
      id: 'vn.gotoModule', label: 'Go to Module Definition', keybindings: [monaco.KeyCode.F12],
      contextMenuGroupId: 'navigation', contextMenuOrder: 1,
      run(ed) {
        const w = ed.getModel().getWordAtPosition(ed.getPosition());
        const m = w && S.modules.find(x => x.name === w.word);
        if (m && S.project) openFile(S.project, m.file, m.line);
        else toast('No module named "' + (w ? w.word : '') + '" in this project');
      }
    });
  }

  // ---------------------------------------------------------------- projects & files
  async function refreshProjects() {
    const r = await api('/api/projects');
    S.projects = r.projects;
    renderTree();
  }

  function fileIcon(f) {
    const b = f.split('/').pop();
    if (/\.vcd$/.test(b)) return vnIcon('wave', 'ficon vcd');
    if (/\.(v|vh|sv)$/.test(b)) return vnIcon('file_v', 'ficon ' + (/^tb/i.test(b) ? 'tb' : 'v'));
    return vnIcon('files', 'ficon other');
  }

  function renderTree() {
    const root = $('#projectTree');
    if (!S.projects.length) {
      root.innerHTML = `<div class="empty-hint">No projects yet.<br><br><button class="btn primary" id="tNew">${vnIcon('plus')}New project</button>
        <button class="btn" id="tEx" style="margin-top:8px">${vnIcon('book')}Open an example</button></div>`;
      $('#tNew').onclick = newProject; $('#tEx').onclick = () => showView('examples');
      return;
    }
    const counts = {};
    S.diagnostics.forEach(d => { const k = S.project + '/' + d.file; counts[k] = counts[k] || { e: 0, w: 0 }; counts[k][d.severity === 'error' ? 'e' : 'w']++; });
    let html = '';
    for (const p of S.projects) {
      const open = S.openProjects.has(p.name);
      html += `<div class="tnode project ${open ? 'open' : ''} ${p.name === S.project ? 'active-project' : ''}" data-project="${esc(p.name)}">
        ${vnIcon('chev', 'chev')}<span class="name">${esc(p.name)}</span>
        <span class="acts">
          <button class="icon-btn sm" data-act="newfile" title="New file">${vnIcon('plus')}</button>
          <button class="icon-btn sm" data-act="renproj" title="Rename project">${vnIcon('edit')}</button>
          <button class="icon-btn sm" data-act="delproj" title="Delete project">${vnIcon('trash')}</button>
        </span></div>`;
      if (open) {
        for (const f of p.files) {
          const key = p.name + '/' + f;
          const tab = S.tabs.find(t => t.key === key);
          const c = counts[key];
          html += `<div class="tnode file ${S.active === key ? 'active' : ''}" data-project="${esc(p.name)}" data-file="${esc(f)}">
            ${fileIcon(f)}<span class="name">${esc(f)}</span>
            ${c && c.e ? `<span class="errdot">${c.e}</span>` : c && c.w ? `<span class="warndot">${c.w}</span>` : ''}
            ${tab && tab.dirty ? '<span class="dirty-dot"></span>' : ''}
            <span class="acts">
              <button class="icon-btn sm" data-act="renfile" title="Rename">${vnIcon('edit')}</button>
              <button class="icon-btn sm" data-act="delfile" title="Delete">${vnIcon('trash')}</button>
            </span></div>`;
        }
        if (!p.files.length) html += `<div class="tnode file" style="color:var(--fg-3)">empty</div>`;
      }
    }
    root.innerHTML = html;
    root.querySelectorAll('.tnode').forEach(n => {
      n.onclick = async e => {
        const act = e.target.closest('[data-act]');
        const project = n.dataset.project, file = n.dataset.file;
        if (!project) return;
        if (act) { e.stopPropagation(); return treeAction(act.dataset.act, project, file); }
        if (file) {
          if (/\.vcd$/.test(file)) return openVcd(project, file);
          return openFile(project, file);
        }
        if (S.openProjects.has(project)) S.openProjects.delete(project); else S.openProjects.add(project);
        setProject(project);
        renderTree();
      };
    });
  }

  async function treeAction(act, project, file) {
    try {
      if (act === 'newfile') {
        const name = await modal({ title: 'New file in ' + project, body: 'File name (e.g. <code>adder.v</code> or <code>tb_adder.v</code>):', input: 'new_module.v', ok: 'Create' });
        if (!name) return;
        const fn = /\.\w+$/.test(name) ? name : name + '.v';
        const mod = fn.replace(/\.\w+$/, '').replace(/\W/g, '_');
        const content = /\.v$/.test(fn) ? '`timescale 1ns / 1ps\n\nmodule ' + mod + ' (\n    \n);\n\nendmodule\n' : '';
        await api('/api/file/create', { project, path: fn, content });
        S.openProjects.add(project);
        await refreshProjects();
        openFile(project, fn, 4);
      } else if (act === 'renproj') {
        const name = await modal({ title: 'Rename project', input: project, ok: 'Rename' });
        if (!name || name === project) return;
        const r = await api('/api/project/rename', { project, name });
        closeTabs(t => t.project === project, true);
        S.openProjects.delete(project); S.openProjects.add(r.name);
        if (S.project === project) S.project = r.name;
        await refreshProjects();
      } else if (act === 'delproj') {
        const ok = await modal({ title: 'Delete project "' + project + '"?', body: 'It will be moved to <code>~/VeriNest/.trash</code>.', ok: 'Delete', danger: true });
        if (!ok) return;
        await api('/api/project/delete', { project });
        closeTabs(t => t.project === project, true);
        if (S.project === project) S.project = null;
        await refreshProjects(); updateCrumbs(); updateTopSelect();
      } else if (act === 'renfile') {
        const name = await modal({ title: 'Rename file', input: file, ok: 'Rename' });
        if (!name || name === file) return;
        await api('/api/file/rename', { project, path: file, new_path: name });
        const t = S.tabs.find(x => x.key === project + '/' + file);
        if (t) {
          const val = t.model.getValue(); const dirty = t.dirty;
          closeTab(t.key, true);
          await openFile(project, name);
          const nt = S.tabs.find(x => x.key === project + '/' + name);
          if (nt && dirty) { nt.model.setValue(val); }
        }
        await refreshProjects();
      } else if (act === 'delfile') {
        const ok = await modal({ title: 'Delete "' + file + '"?', body: 'It will be moved to <code>~/VeriNest/.trash</code>.', ok: 'Delete', danger: true });
        if (!ok) return;
        await api('/api/file/delete', { project, path: file });
        closeTab(project + '/' + file, true);
        await refreshProjects();
        scheduleLint(50);
      }
    } catch (e) { toast(e.message, true); }
  }

  async function newProject() {
    const name = await modal({ title: 'New project', body: 'Project name:', input: 'my_design', ok: 'Create' });
    if (!name) return;
    try {
      const r = await api('/api/project/create', { name });
      S.openProjects.add(r.name);
      await refreshProjects();
      showView('explorer');
      const p = S.projects.find(x => x.name === r.name);
      if (p && p.files[0]) openFile(r.name, p.files[0]);
    } catch (e) { toast(e.message, true); }
  }

  function setProject(name) {
    if (S.project === name) return;
    S.project = name;
    S.diagnostics = []; S.modules = [];
    renderProblems(); updateTopSelect(); updateCrumbs();
    scheduleLint(30);
  }

  // ---------------------------------------------------------------- tabs
  async function openFile(project, path, line) {
    const key = project + '/' + path;
    let tab = S.tabs.find(t => t.key === key);
    if (!tab) {
      let content;
      try { content = (await api('/api/file', null, { project, path })).content; } catch (e) { return toast(e.message, true); }
      const lang = /\.(v|vh|sv)$/.test(path) ? 'verilog' : /\.md$/.test(path) ? 'markdown' : 'plaintext';
      const model = monaco.editor.createModel(content, lang, monaco.Uri.parse('inmemory://verinest/' + encodeURIComponent(project) + '/' + path));
      model.updateOptions({ tabSize: 4, insertSpaces: true });
      tab = { key, project, path, model, dirty: false, saved: content, view: null };
      model.onDidChangeContent(() => {
        const d = model.getValue() !== tab.saved;
        if (d !== tab.dirty) { tab.dirty = d; renderTabs(); renderTree(); }
        if (tab.project === S.project && lang === 'verilog') scheduleLint();
      });
      S.tabs.push(tab);
    }
    activateTab(key);
    if (line) {
      editor.revealLineInCenter(line);
      editor.setPosition({ lineNumber: line, column: 1 });
    }
    editor.focus();
  }

  function activateTab(key) {
    const cur = S.tabs.find(t => t.key === S.active);
    if (cur) cur.view = editor.saveViewState();
    const tab = S.tabs.find(t => t.key === key);
    if (!tab) return;
    S.active = key;
    editor.setModel(tab.model);
    if (tab.view) editor.restoreViewState(tab.view);
    $('#welcome').classList.add('hidden');
    S.openProjects.add(tab.project);
    setProject(tab.project);
    renderTabs(); renderTree(); updateCrumbs(); applyMarkers();
  }

  function renderTabs() {
    const c = {};
    S.diagnostics.forEach(d => { const k = S.project + '/' + d.file; if (d.severity === 'error') c[k] = (c[k] || 0) + 1; });
    $('#tabs').innerHTML = S.tabs.map(t => `
      <div class="tab ${t.key === S.active ? 'active' : ''} ${t.dirty ? 'dirty' : ''}" data-key="${esc(t.key)}" title="${esc(t.key)}">
        ${fileIcon(t.path)}<span>${esc(t.path.split('/').pop())}</span>
        ${c[t.key] ? `<span class="tcount" style="color:var(--err)">${c[t.key]}</span>` : ''}
        <span class="x" title="Close">${vnIcon('close')}</span></div>`).join('');
    $$('#tabs .tab').forEach(el => {
      el.onclick = e => { if (e.target.closest('.x')) closeTab(el.dataset.key); else activateTab(el.dataset.key); };
      el.onauxclick = e => { if (e.button === 1) closeTab(el.dataset.key); };
    });
  }

  async function closeTab(key, force) {
    const i = S.tabs.findIndex(t => t.key === key);
    if (i < 0) return;
    const t = S.tabs[i];
    if (t.dirty && !force) {
      const ok = await modal({ title: 'Close "' + t.path + '"?', body: 'You have unsaved changes. Save them first?', ok: 'Save & close' });
      if (ok === null) return;
      await saveTab(t);
    }
    S.tabs.splice(i, 1);
    t.model.dispose();
    if (S.active === key) {
      const n = S.tabs[i] || S.tabs[i - 1];
      if (n) activateTab(n.key);
      else { S.active = null; editor.setModel(null); $('#welcome').classList.remove('hidden'); updateCrumbs(); }
    }
    renderTabs(); renderTree();
  }
  function closeTabs(pred, force) { S.tabs.filter(pred).map(t => t.key).forEach(k => closeTab(k, force)); }

  async function saveTab(t) {
    const content = t.model.getValue();
    await api('/api/file/save', { project: t.project, path: t.path, content });
    t.saved = content; t.dirty = false;
  }
  async function saveActive() {
    const t = S.tabs.find(x => x.key === S.active);
    if (!t) return;
    try { await saveTab(t); renderTabs(); renderTree(); toast('Saved ' + t.path); } catch (e) { toast(e.message, true); }
  }
  async function saveAll(project) {
    for (const t of S.tabs) if (t.dirty && (!project || t.project === project)) await saveTab(t);
    renderTabs(); renderTree();
  }

  function updateCrumbs() {
    const t = S.tabs.find(x => x.key === S.active);
    $('#crumbs').innerHTML = S.project ? `<b>${esc(S.project)}</b>${t && t.project === S.project ? ' / ' + esc(t.path) : ''}` : '';
  }

  function buffers(project) {
    const files = {};
    S.tabs.forEach(t => { if (t.project === project && /\.(v|vh|sv)$/.test(t.path)) files[t.path] = t.model.getValue(); });
    return files;
  }

  // ---------------------------------------------------------------- lint & problems
  function scheduleLint(ms) {
    clearTimeout(S.lintTimer);
    S.lintTimer = setTimeout(() => lintNow(false), ms == null ? 700 : ms);
  }

  async function lintNow(showPanel) {
    if (!S.project) return;
    const seq = ++S.lintSeq;
    const project = S.project;
    try {
      const r = await api('/api/lint', { project, files: buffers(project) });
      if (seq !== S.lintSeq || project !== S.project) return;
      S.diagnostics = r.diagnostics; S.modules = r.modules;
      renderProblems(); applyMarkers(); updateTopSelect(); renderTabs(); renderTree();
      if (showPanel) {
        showPanel_('problems');
        const e = r.diagnostics.filter(d => d.severity === 'error').length;
        toast(e ? e + ' error(s) found' : 'No errors found ✓', e > 0);
      }
    } catch (e) { if (showPanel) toast(e.message, true); }
  }

  function markerMessage(d) {
    let m = (d.title ? d.title + ': ' : '') + d.message;
    if (d.explain) m += '\n\n' + d.explain;
    if (d.fix) m += '\nFix: ' + d.fix;
    return m;
  }

  function applyMarkers() {
    if (!monaco) return;
    S.tabs.forEach(t => {
      if (t.project !== S.project) { monaco.editor.setModelMarkers(t.model, 'verinest', []); return; }
      const ds = S.diagnostics.filter(d => d.file === t.path);
      const markers = ds.map(d => {
        const lineLen = d.line <= t.model.getLineCount() ? t.model.getLineMaxColumn(d.line) : 1;
        const line = Math.min(d.line, t.model.getLineCount());
        const lineText = t.model.getLineContent(line);
        const first = (lineText.match(/^\s*/)[0].length) + 1;
        const col = d.col > 1 ? d.col : first;
        return {
          startLineNumber: line, endLineNumber: line, startColumn: col, endColumn: Math.max(col + 1, lineLen),
          message: markerMessage(d), source: d.source + (d.code ? ' ' + d.code : ''),
          severity: d.severity === 'error' ? monaco.MarkerSeverity.Error : monaco.MarkerSeverity.Warning,
        };
      });
      // highlight the line that probably misses a ';'
      ds.filter(d => d.related_line).forEach(d => {
        const ln = d.related_line;
        if (ln <= t.model.getLineCount()) markers.push({
          startLineNumber: ln, endLineNumber: ln, startColumn: t.model.getLineMaxColumn(ln) - 1, endColumn: t.model.getLineMaxColumn(ln),
          message: "Probably missing ';' here", severity: monaco.MarkerSeverity.Error, source: 'verinest',
        });
      });
      monaco.editor.setModelMarkers(t.model, 'verinest', markers);
    });
    updateStatus();
  }

  function renderProblems() {
    const ds = S.diagnostics;
    const e = ds.filter(d => d.severity === 'error').length, w = ds.length - e;
    const b = $('#probBadge');
    b.textContent = ds.length; b.className = 'badge' + (e ? ' err' : w ? ' warn' : '');
    const root = $('#problems');
    if (!S.project) { root.innerHTML = '<div class="no-problems">Open a project to check it.</div>'; updateStatus(); return; }
    if (!ds.length) {
      root.innerHTML = `<div class="no-problems">${vnIcon('check')} No problems in <b>${esc(S.project)}</b></div>`;
      updateStatus(); return;
    }
    const groups = {};
    ds.forEach((d, i) => { (groups[d.file] = groups[d.file] || []).push([d, i]); });
    let html = '';
    for (const f of Object.keys(groups)) {
      html += `<div class="pgroup-head">${fileIcon(f)}${esc(f)}<span class="badge">${groups[f].length}</span></div>`;
      for (const [d, i] of groups[f]) {
        html += `<div class="prob ${d.severity} ${S.selectedProblem === i ? 'sel' : ''}" data-i="${i}">
          <div class="prob-row">${vnIcon(d.severity === 'error' ? 'error' : 'warning')}
            <span class="prob-title">${esc(d.title || (d.severity === 'error' ? 'Error' : 'Warning'))}</span>
            <span class="prob-msg">${esc(d.message)}</span>
            <span class="prob-src">${esc(d.source)}${d.code ? ' ' + esc(d.code) : ''}</span>
            <span class="prob-loc">Ln ${d.line}</span></div>
          <div class="prob-detail">
            ${d.explain ? `<p>${esc(d.explain)}</p>` : ''}
            ${d.fix ? `<p class="fix"><b>How to fix:</b> ${esc(d.fix)}</p>` : ''}
            <div class="raw">${esc(d.source)}: ${esc(d.message)}</div>
          </div></div>`;
      }
    }
    root.innerHTML = html;
    root.querySelectorAll('.prob').forEach(el => {
      el.onclick = () => {
        const i = +el.dataset.i, d = S.diagnostics[i];
        S.selectedProblem = S.selectedProblem === i ? null : i;
        renderProblems();
        openFile(S.project, d.file, d.line);
      };
    });
    updateStatus();
  }

  function updateStatus() {
    const e = S.diagnostics.filter(d => d.severity === 'error').length, w = S.diagnostics.length - e;
    $('#sbProblems').innerHTML = `<span class="${e ? 'sb-err' : ''}">${vnIcon('error')} ${e}</span><span class="${w ? 'sb-warn' : ''}">${vnIcon('warning')} ${w}</span>`;
  }

  // ---------------------------------------------------------------- top module
  function updateTopSelect() {
    const sel = $('#topSelect');
    const mods = S.modules.filter(m => m.is_top);
    const choice = S.topChoice[S.project] || '';
    const tbs = mods.filter(m => m.is_tb), others = mods.filter(m => !m.is_tb);
    let html = '<option value="">auto</option>';
    if (tbs.length) html += '<optgroup label="Testbenches">' + tbs.map(m => `<option value="${esc(m.name)}">${esc(m.name)}</option>`).join('') + '</optgroup>';
    if (others.length) html += '<optgroup label="Modules">' + others.map(m => `<option value="${esc(m.name)}">${esc(m.name)}</option>`).join('') + '</optgroup>';
    sel.innerHTML = html;
    sel.value = mods.some(m => m.name === choice) ? choice : '';
    const auto = guessTop();
    sel.options[0].textContent = auto ? 'auto (' + auto + ')' : 'auto';
  }
  function guessTop() {
    const t = S.tabs.find(x => x.key === S.active);
    const tbs = S.modules.filter(m => m.is_tb && m.is_top);
    if (t) { const here = tbs.find(m => m.file === t.path); if (here) return here.name; }
    if (tbs.length) return tbs[0].name;
    const tops = S.modules.filter(m => m.is_top);
    return tops.length ? tops[0].name : '';
  }

  // ---------------------------------------------------------------- run
  let running = false;
  async function run() {
    if (running) return;
    if (!S.project) return toast('Open a project or an example first', true);
    if (!S.tools.iverilog || !S.tools.iverilog.path) {
      return modal({ title: 'Icarus Verilog not found', body: 'Install it with:<br><code>sudo apt install iverilog</code>', cancel: false });
    }
    running = true;
    const project = S.project;
    setRunStatus('busy', 'Compiling & simulating…');
    try {
      await saveAll(project);
      const t = S.tabs.find(x => x.key === S.active);
      const top = $('#topSelect').value || null;
      const r = await api('/api/simulate', { project, top, current: t && t.project === project ? t.path : null });
      S.modules = r.modules || S.modules;
      updateTopSelect();
      // keep lint warnings, replace errors with compile result
      if (r.diagnostics && r.diagnostics.length) {
        S.diagnostics = r.diagnostics.concat(S.diagnostics.filter(d => d.severity !== 'error'));
        renderProblems(); applyMarkers(); renderTabs();
      }
      renderConsole(r);
      if (r.vcd) {
        wave.load(r.vcd);
      }
      if (r.phase === 'compile' && !r.ok) {
        setRunStatus('bad', 'Compile failed');
        showPanel_(r.diagnostics && r.diagnostics.length ? 'problems' : 'console');
      } else if (r.timeout) {
        setRunStatus('bad', 'Timed out');
        showPanel_(r.vcd ? 'wave' : 'console');
      } else {
        const label = r.failed ? 'FAIL' : r.passed ? 'PASS' : 'Done';
        setRunStatus(r.failed ? 'bad' : 'ok', label + ' · ' + r.top + ' · ' + r.elapsed + 's');
        showPanel_(r.vcd ? 'wave' : 'console');
        if (r.failed) toast('Testbench reported failures — see Console', true);
      }
      scheduleLint(100);
      refreshProjects();   // show the new .vcd file in the explorer
    } catch (e) {
      setRunStatus('bad', 'Error'); toast(e.message, true);
    } finally { running = false; }
  }

  function setRunStatus(kind, text) {
    const el = $('#runStatus');
    el.className = 'run-status ' + (kind === 'ok' ? 'ok' : kind === 'bad' ? 'bad' : '');
    el.innerHTML = (kind === 'busy' ? '<span class="spin"></span>' : '') + esc(text);
  }

  function renderConsole(r) {
    const c = $('#console');
    let html = `<span class="c-head">$ iverilog -g2005 … -s ${esc(r.top || '?')} &amp;&amp; vvp sim.vvp   (${r.elapsed || 0}s)</span>\n`;
    if (r.error) html += `<span class="c-bad">${esc(r.error)}</span>\n`;
    if (r.compile_output && r.compile_output.trim()) html += `<span class="c-warn">${esc(r.compile_output.trim())}</span>\n`;
    const out = (r.stdout || '').replace(/^VCD info: dumpfile .*$/m, '');
    html += esc(out)
      .replace(/^(.*\b(PASS(ED)?|OK)\b.*)$/gm, '<span class="c-ok">$1</span>')
      .replace(/^(.*\b(FAIL(ED)?|ERROR|MISMATCH)\b.*)$/gm, '<span class="c-bad">$1</span>');
    if (r.phase === 'run' && !r.timeout) {
      const cls = r.failed ? 'bad' : r.passed ? 'ok' : 'neutral';
      const txt = r.failed ? '✗ Testbench reported failures' : r.passed ? '✓ All checks passed' : '■ Simulation finished';
      html += `\n<span class="c-banner ${cls}">${txt}</span>`;
      if (r.vcd) html += `  <span class="c-head">waveform: ${esc(r.vcd_file || '')} (${Object.keys(r.vcd.signals).length} signals)</span>`;
    }
    c.innerHTML = html;
  }

  async function openVcd(project, file) {
    try {
      const d = await api('/api/vcd', null, { project, path: file });
      setProject(project);
      wave.load(d);
      showPanel_('wave');
      if ($('#panel').classList.contains('collapsed')) togglePanel();
    } catch (e) { toast(e.message, true); }
  }

  // ---------------------------------------------------------------- format & testbench
  async function formatActive() {
    const t = S.tabs.find(x => x.key === S.active);
    if (!t || t.model.getLanguageId() !== 'verilog') return;
    try {
      const r = await api('/api/format', { content: t.model.getValue() });
      if (r.content === t.model.getValue()) return toast('Code is already clean ✓');
      const sel = editor.getSelections();
      editor.pushUndoStop();
      editor.executeEdits('verinest-format', [{ range: t.model.getFullModelRange(), text: r.content }]);
      editor.pushUndoStop();
      if (sel) editor.setSelections(sel);
      toast('Code cleaned up (Ctrl+Z to undo)');
    } catch (e) { toast(e.message, true); }
  }

  async function generateTb() {
    const t = S.tabs.find(x => x.key === S.active);
    if (!t || !/\.v$/.test(t.path)) return toast('Open a Verilog module file first', true);
    try {
      const r = await api('/api/tbgen', { content: t.model.getValue(), file: t.path });
      const proj = S.projects.find(p => p.name === t.project);
      let fn = r.filename;
      if (proj && proj.files.includes(fn)) {
        const ok = await modal({ title: fn + ' already exists', body: 'Create a new copy instead of overwriting?', ok: 'Create copy' });
        if (!ok) return;
        let k = 2; while (proj.files.includes(fn.replace(/\.v$/, '_' + k + '.v'))) k++;
        fn = fn.replace(/\.v$/, '_' + k + '.v');
      }
      // module name must match the (possibly renamed) file, or two modules would clash
      const tbName = fn.replace(/\.v$/, '');
      const content = r.content.split(r.filename.replace(/\.v$/, '')).join(tbName);
      await api('/api/file/create', { project: t.project, path: fn, content });
      await refreshProjects();
      await openFile(t.project, fn);
      toast('Testbench for "' + r.module + '" created — press F5 to run it');
    } catch (e) { toast(e.message, true); }
  }

  // ---------------------------------------------------------------- examples
  async function loadExamples() {
    const r = await api('/api/examples');
    S.examples = r.examples;
    $('#exampleList').innerHTML = S.examples.map(ex => `
      <div class="ex-card" data-id="${esc(ex.id)}">
        <h4>${esc(ex.title)} <span class="lvl ${esc(ex.level)}">${esc(ex.level)}</span></h4>
        <p>${esc(ex.description)}</p>
      </div>`).join('');
    $$('#exampleList .ex-card').forEach(c => c.onclick = () => openExample(c.dataset.id));
  }

  async function openExample(id) {
    try {
      const r = await api('/api/examples/open', { id });
      S.openProjects.add(r.name);
      await refreshProjects();
      showView('explorer');
      const p = S.projects.find(x => x.name === r.name);
      const first = (r.meta && r.meta.open) || (p && p.files.find(f => /\.v$/.test(f) && !/^tb/.test(f))) || (p && p.files[0]);
      if (first) await openFile(r.name, first);
      if (r.meta && r.meta.top) { S.topChoice[r.name] = ''; }
      toast('Example opened as project "' + r.name + '" — press F5 to simulate');
    } catch (e) { toast(e.message, true); }
  }

  // ---------------------------------------------------------------- layout
  function showView(v) {
    $$('.act').forEach(a => a.classList.toggle('active', a.dataset.view === v));
    $$('.view').forEach(x => x.classList.toggle('active', x.id === 'view-' + v));
  }
  function showPanel_(p) {
    $$('.ptab').forEach(a => a.classList.toggle('active', a.dataset.panel === p));
    $$('.pview').forEach(x => x.classList.toggle('active', x.id === 'panel-' + p));
    if ($('#panel').classList.contains('collapsed')) togglePanel();
    if (p === 'wave') setTimeout(() => wave.resize(), 0);
  }
  function togglePanel() {
    $('#panel').classList.toggle('collapsed');
    $('#btnPanelHide').innerHTML = vnIcon($('#panel').classList.contains('collapsed') ? 'up' : 'down');
    setTimeout(() => wave.resize(), 0);
  }
  let panelMax = false, panelPrevH = 300;
  function toggleMax() {
    const p = $('#panel');
    if (!panelMax) { panelPrevH = p.offsetHeight; p.style.height = ($('#work').offsetHeight - 80) + 'px'; }
    else p.style.height = panelPrevH + 'px';
    panelMax = !panelMax;
    $('#btnPanelMax').innerHTML = vnIcon(panelMax ? 'min' : 'max');
    p.classList.remove('collapsed');
    setTimeout(() => wave.resize(), 0);
  }

  function initResizers() {
    const drag = (el, onMove) => {
      el.addEventListener('mousedown', e => {
        e.preventDefault();
        el.classList.add('dragging');
        const move = ev => onMove(ev);
        const up = () => { el.classList.remove('dragging'); window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); wave && wave.resize(); };
        window.addEventListener('mousemove', move); window.addEventListener('mouseup', up);
      });
    };
    drag($('#sideResizer'), e => { $('#sidebar').style.width = Math.min(520, Math.max(180, e.clientX - 48)) + 'px'; });
    drag($('#panelResizer'), e => {
      const work = $('#work').getBoundingClientRect();
      const h = Math.min(work.height - 80, Math.max(80, work.bottom - e.clientY));
      $('#panel').style.height = h + 'px'; $('#panel').classList.remove('collapsed');
      wave && wave.resize();
    });
  }

  function showHelp() {
    modal({
      title: 'VeriNest — shortcuts', cancel: false, ok: 'Close',
      body: `<table>
        <tr><td><kbd>F5</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>B</kbd></td><td>Run simulation</td></tr>
        <tr><td><kbd>Ctrl</kbd>+<kbd>S</kbd></td><td>Save file</td></tr>
        <tr><td><kbd>Tab</kbd> or <kbd>Enter</kbd></td><td>Accept the grey suggestion</td></tr>
        <tr><td><kbd>Esc</kbd></td><td>Dismiss the suggestion</td></tr>
        <tr><td><kbd>Shift</kbd>+<kbd>Alt</kbd>+<kbd>F</kbd></td><td>Clean code (format)</td></tr>
        <tr><td><kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>L</kbd></td><td>Check for errors</td></tr>
        <tr><td><kbd>Ctrl</kbd>+<kbd>J</kbd></td><td>Show / hide bottom panel</td></tr>
        <tr><td><kbd>F12</kbd> on a module name</td><td>Go to its definition</td></tr>
        <tr><td colspan="2" style="padding-top:10px;color:var(--fg-3)">Waveform: <kbd>Ctrl</kbd>+wheel zoom · drag to pan · click = cursor · <kbd>Shift</kbd>+click = marker · <kbd>←</kbd>/<kbd>→</kbd> jump to edges · <kbd>F</kbd> fit · <kbd>Del</kbd> remove signal</td></tr>
        </table><p style="margin-top:12px;color:var(--fg-3)">Workspace: <code>${esc(S.workspace || '~/VeriNest')}</code></p>`,
    });
  }

  function renderTools() {
    const t = S.tools;
    const item = (n, label) => `<span class="${t[n] && t[n].path ? 'tool-ok' : 'tool-miss'}" title="${esc((t[n] && t[n].version) || 'not installed')}">● ${label}</span>`;
    $('#sbTools').innerHTML = item('iverilog', 'Icarus') + '&nbsp;&nbsp;' + item('verilator', 'Verilator');
  }

  // ---------------------------------------------------------------- boot
  async function boot() {
    $('#btnTheme').innerHTML = vnIcon(S.theme === 'dark' ? 'sun' : 'moon');
    initResizers();
    wave = new VNWave.WaveView($('#wave'));
    await initMonaco();
    const st = await api('/api/state');
    S.tools = st.tools; S.workspace = st.workspace;
    if (st.settings && st.settings.theme && !localStorage.getItem('vn-theme')) applyTheme(st.settings.theme);
    renderTools();
    await Promise.all([refreshProjects(), loadExamples()]);
    renderProblems(); updateStatus();

    $('#btnRun').onclick = run;
    $('#btnCheck').onclick = () => lintNow(true);
    $('#btnFormat').onclick = formatActive;
    $('#btnTb').onclick = generateTb;
    $('#btnTheme').onclick = () => { applyTheme(S.theme === 'dark' ? 'light' : 'dark'); api('/api/settings', { theme: S.theme }).catch(() => { }); };
    $('#btnHelp').onclick = showHelp;
    $('#btnNewProject').onclick = newProject;
    $('#wNew').onclick = newProject;
    $('#wExample').onclick = () => showView('examples');
    $('#btnPanelHide').onclick = togglePanel;
    $('#btnPanelMax').onclick = toggleMax;
    $('#sbProblems').onclick = () => showPanel_('problems');
    $('#topSelect').onchange = e => { S.topChoice[S.project] = e.target.value; };
    $$('.act').forEach(a => a.onclick = () => showView(a.dataset.view));
    $$('.ptab').forEach(a => a.onclick = () => showPanel_(a.dataset.panel));
    window.addEventListener('keydown', e => {
      if (e.key === 'F5') { e.preventDefault(); run(); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveActive(); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'j') { e.preventDefault(); togglePanel(); }
    });
    window.addEventListener('beforeunload', e => { if (S.tabs.some(t => t.dirty)) { e.preventDefault(); e.returnValue = ''; } });
    setInterval(() => api('/api/ping').catch(() => { }), 5000);
    api('/api/ping').catch(() => { });
    // reopen the most recent project
    if (S.projects.length) {
      const recent = [...S.projects].sort((a, b) => b.mtime - a.mtime)[0];
      S.openProjects.add(recent.name); setProject(recent.name); renderTree();
    }
  }

  window.addEventListener('unhandledrejection', e => { if (e.reason && (e.reason.name === 'Canceled' || e.reason.message === 'Canceled')) e.preventDefault(); });
  window.VN = { S, api, run, openFile, openExample, applyTheme, showPanel: showPanel_, get wave() { return wave; }, get editor() { return editor; } };
  boot().catch(e => { console.error(e); toast('Startup error: ' + e.message, true); });
})();
