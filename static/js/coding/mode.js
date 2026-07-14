/**
 * Coding Mode — first-class Spark engineering workspace.
 * Engine-agnostic (Harness Layer). Does not replace Chat.
 */
import { CodingAPI } from './api.js';

const AGENTS = [
  'Architect', 'Backend', 'Frontend', 'Database',
  'Security', 'Performance', 'Documentation', 'Testing',
];

const EXEC_STAGES = [
  'User Action', 'Frontend', 'State', 'API', 'Business Logic',
  'Database', 'Response', 'UI Update',
];

export class CodingMode {
  constructor() {
    this.root = null;
    this.workspaceId = null;
    this.manifest = null;
    this.twinId = null;
    this.openFiles = new Map(); // path -> { content, dirty }
    this.activePath = null;
    this.xray = false;
    this.learning = false;
    this.leftTab = 'explorer';
    this.bottomTab = 'output';
    this.agent = 'Architect';
    this.graphIndex = null; // name -> node for xray
    this.graphEdges = [];   // twin edges for xray walks
    this._xrayCache = new Map(); // nodeId -> last dep summary
    this._execTimer = null;
    this._bound = false;
    this._xrayTimer = null;
  }

  async open() {
    this._ensureDom();
    this.root.classList.add('open');
    document.body.classList.add('coding-mode-open');
    await this._refreshWorkspaces();
    if (this.workspaceId) await this._loadWorkspace(this.workspaceId);
  }

  close() {
    if (this.root) this.root.classList.remove('open');
    document.body.classList.remove('coding-mode-open');
    if (this._execTimer) clearInterval(this._execTimer);
    // Restore chat shell URL without full reload
    if (location.pathname === '/coding') {
      history.pushState({}, '', '/');
    }
  }

  isOpen() {
    return !!(this.root && this.root.classList.contains('open'));
  }

  toggle() {
    if (this.isOpen()) this.close();
    else this.open();
  }

  _ensureDom() {
    if (this.root) return;
    // Load CSS once
    if (!document.getElementById('coding-mode-css')) {
      const link = document.createElement('link');
      link.id = 'coding-mode-css';
      link.rel = 'stylesheet';
      link.href = '/static/js/coding/styles.css';
      document.head.appendChild(link);
    }
    this.root = document.createElement('div');
    this.root.id = 'coding-mode-root';
    this.root.innerHTML = this._shellHtml();
    document.body.appendChild(this.root);
    this._bind();
  }

  _shellHtml() {
    return `
      <div class="cm-topbar">
        <span class="cm-brand">Coding</span>
        <select class="cm-ws-select" data-role="ws-select" title="Workspace"></select>
        <button type="button" class="cm-btn" data-act="new-ws" title="New workspace">+ Workspace</button>
        <span class="cm-chip" data-chip="branch"><strong>branch</strong> —</span>
        <span class="cm-chip" data-chip="harness"><strong>harness</strong> —</span>
        <span class="cm-chip" data-chip="runtime"><strong>runtime</strong> —</span>
        <span class="cm-chip" data-chip="model"><strong>model</strong> —</span>
        <span class="cm-chip" data-chip="twin"><strong>twin</strong> —</span>
        <span class="cm-chip" data-chip="sync"><strong>sync</strong> —</span>
        <div class="cm-topbar-actions">
          <button type="button" class="cm-btn" data-act="xray" title="X-Ray mode">X-Ray</button>
          <button type="button" class="cm-btn" data-act="learning" title="Learning mode">Learn</button>
          <button type="button" class="cm-btn" data-act="exec" title="Explain execution">Execution</button>
          <button type="button" class="cm-btn" data-act="ensure-twin">Sync Twin</button>
          <button type="button" class="cm-btn" data-act="start-harness">Start Harness</button>
          <button type="button" class="cm-btn" data-act="twin-ui">Semantic Twin</button>
          <button type="button" class="cm-btn" data-act="os-ui">Spark OS</button>
          <button type="button" class="cm-btn primary" data-act="close">Close</button>
        </div>
      </div>
      <div class="cm-body">
        <aside class="cm-left">
          <div class="cm-left-nav">
            <button type="button" data-left="explorer" class="active">Explorer</button>
            <button type="button" data-left="search">Search</button>
            <button type="button" data-left="git">Git</button>
            <button type="button" data-left="twin">Twin</button>
            <button type="button" data-left="runtime">Runtime</button>
            <button type="button" data-left="knowledge">Knowledge</button>
            <button type="button" data-left="terminal">Terminal</button>
          </div>
          <div class="cm-tree" data-role="tree"></div>
          <div class="cm-left-panel hidden" data-role="left-panel"></div>
        </aside>
        <main class="cm-center">
          <div class="cm-tabs" data-role="tabs"></div>
          <div class="cm-editor-wrap" data-role="editor-wrap">
            <div class="cm-editor-empty" data-role="empty">Select a workspace file to edit.<br><span class="cm-muted">Coding Mode is harness-agnostic — OpenCode is the first engine.</span></div>
          </div>
          <div class="cm-xray-tooltip" data-role="xray-tip"></div>
        </main>
        <aside class="cm-right">
          <div class="cm-right-header">AI Assistant</div>
          <div class="cm-agents" data-role="agents">
            ${AGENTS.map((a) => `<button type="button" data-agent="${a}" class="${a === 'Architect' ? 'active' : ''}">${a}</button>`).join('')}
          </div>
          <div class="cm-actions">
            <button type="button" data-cmd="ask">Ask</button>
            <button type="button" data-cmd="edit">Edit</button>
            <button type="button" data-cmd="refactor">Refactor</button>
            <button type="button" data-cmd="explain">Explain</button>
            <button type="button" data-cmd="generate">Generate</button>
            <button type="button" data-cmd="review">Review</button>
            <button type="button" data-cmd="test">Test</button>
            <button type="button" data-cmd="debug">Debug</button>
            <button type="button" data-cmd="quiz">Quiz</button>
            <button type="button" data-cmd="tutorial">Tutorial</button>
            <button type="button" data-cmd="simulate">Simulate</button>
          </div>
          <div class="cm-chat" data-role="chat">
            <div class="cm-msg assistant"><div class="role">Assistant</div><div class="bubble">Coding Mode is ready. Select a workspace, open a file, and ask anything — explanations come from the Semantic Twin.</div></div>
          </div>
          <div class="cm-explain-panel hidden" data-role="explain"></div>
          <div class="cm-composer">
            <textarea data-role="input" placeholder="Ask about this code, refactor, explain, review…" rows="2"></textarea>
            <button type="button" class="cm-btn primary" data-act="send">Send</button>
          </div>
        </aside>
        <div class="cm-bottom">
          <div class="cm-bottom-tabs">
            <button type="button" data-bottom="output" class="active">Output</button>
            <button type="button" data-bottom="problems">Problems</button>
            <button type="button" data-bottom="terminal">Terminal</button>
            <button type="button" data-bottom="logs">Logs</button>
            <button type="button" data-bottom="execution">Execution</button>
          </div>
          <div class="cm-bottom-body" data-role="bottom">Ready.</div>
        </div>
      </div>
    `;
  }

  _bind() {
    if (this._bound) return;
    this._bound = true;
    const r = this.root;

    r.querySelector('[data-act="close"]').addEventListener('click', () => this.close());
    r.querySelector('[data-act="xray"]').addEventListener('click', (e) => {
      this.xray = !this.xray;
      e.currentTarget.classList.toggle('active', this.xray);
      const ed = r.querySelector('.cm-editor');
      if (ed) ed.classList.toggle('xray-on', this.xray);
      this._log(this.xray ? 'X-Ray on — hover symbols for twin relationships.' : 'X-Ray off.');
    });
    r.querySelector('[data-act="learning"]').addEventListener('click', (e) => {
      this.learning = !this.learning;
      e.currentTarget.classList.toggle('active', this.learning);
      this._log(this.learning ? 'Learning mode on — explain/quiz/tutorial available.' : 'Learning mode off.');
    });
    r.querySelector('[data-act="exec"]').addEventListener('click', () => this._runExecutionAnimation());
    r.querySelector('[data-act="ensure-twin"]').addEventListener('click', () => this._ensureTwin());
    r.querySelector('[data-act="start-harness"]').addEventListener('click', () => this._startHarness());
    r.querySelector('[data-act="twin-ui"]').addEventListener('click', () => {
      const q = this.twinId ? `?twin=${encodeURIComponent(this.twinId)}` : '';
      window.open(`/semantic-twin${q}`, '_blank');
    });
    r.querySelector('[data-act="os-ui"]').addEventListener('click', () => {
      const q = this.twinId ? `?twin=${encodeURIComponent(this.twinId)}` : '';
      window.open(`/spark-os${q}`, '_blank');
    });
    r.querySelector('[data-act="new-ws"]').addEventListener('click', () => this._newWorkspace());
    r.querySelector('[data-act="send"]').addEventListener('click', () => this._send());
    r.querySelector('[data-role="input"]').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        this._send();
      }
    });
    r.querySelector('[data-role="ws-select"]').addEventListener('change', async (e) => {
      if (e.target.value) await this._loadWorkspace(e.target.value);
    });

    r.querySelectorAll('[data-left]').forEach((btn) => {
      btn.addEventListener('click', () => this._setLeft(btn.dataset.left));
    });
    r.querySelectorAll('[data-bottom]').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.bottomTab = btn.dataset.bottom;
        r.querySelectorAll('[data-bottom]').forEach((b) => b.classList.toggle('active', b === btn));
        this._renderBottom();
      });
    });
    r.querySelectorAll('[data-agent]').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.agent = btn.dataset.agent;
        r.querySelectorAll('[data-agent]').forEach((b) => b.classList.toggle('active', b === btn));
        this._assistant(`Switched to **${this.agent}** agent.`);
      });
    });
    r.querySelectorAll('[data-cmd]').forEach((btn) => {
      btn.addEventListener('click', () => this._command(btn.dataset.cmd));
    });

    document.addEventListener('keydown', (e) => {
      if (!this.isOpen()) return;
      if (e.key === 'Escape') {
        // Don't steal from nested inputs if needed — still close mode is OK for Escape
        if (e.target.closest('.cm-composer textarea')) return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        this._saveActive();
      }
    });
  }

  async _refreshWorkspaces() {
    const sel = this.root.querySelector('[data-role="ws-select"]');
    try {
      const data = await CodingAPI.listWorkspaces();
      const list = data.workspaces || [];
      sel.innerHTML = `<option value="">Select workspace…</option>` +
        list.map((w) =>
          `<option value="${esc(w.workspace_id)}">${esc(w.name)}</option>`
        ).join('');
      if (this.workspaceId) sel.value = this.workspaceId;
      else if (list[0]) {
        sel.value = list[0].workspace_id;
        this.workspaceId = list[0].workspace_id;
      }
    } catch (err) {
      sel.innerHTML = `<option value="">${esc(err.message)}</option>`;
    }
  }

  async _loadWorkspace(id) {
    this.workspaceId = id;
    try {
      this.manifest = await CodingAPI.getWorkspace(id);
      this.twinId = this.manifest.twin_id || null;
      const st = await CodingAPI.status(id);
      this._paintStatus(st);
      await this._loadTree('');
      if (this.twinId) await this._indexTwin();
      this._log(`Workspace ${this.manifest.name} ready.`);
    } catch (err) {
      this._log(`Error: ${err.message}`);
    }
  }

  _paintStatus(st) {
    const m = st.manifest || this.manifest || {};
    setChip(this.root, 'branch', m.branch || '—');
    setChip(this.root, 'harness', m.active_harness || st.harness_state || '—');
    setChip(this.root, 'runtime', m.runtime_profile || 'default');
    setChip(this.root, 'model', m.active_model || '—');
    const twinEl = this.root.querySelector('[data-chip="twin"]');
    if (twinEl) {
      twinEl.innerHTML = `<strong>twin</strong> ${esc(st.twin_status || '—')}`;
      twinEl.className = 'cm-chip ' + (st.twin_status === 'ready' ? 'ok' : 'warn');
    }
    const syncEl = this.root.querySelector('[data-chip="sync"]');
    if (syncEl) {
      syncEl.innerHTML = `<strong>sync</strong> ${esc(st.sync_status || '—')}`;
      syncEl.className = 'cm-chip ' + (st.sync_status === 'live' ? 'ok' : 'warn');
    }
  }

  async _loadTree(path) {
    if (!this.workspaceId) return;
    const tree = this.root.querySelector('[data-role="tree"]');
    tree.classList.remove('hidden');
    this.root.querySelector('[data-role="left-panel"]').classList.add('hidden');
    try {
      const data = await CodingAPI.listFiles(this.workspaceId, path);
      const entries = data.entries || [];
      const up = path ? path.split('/').slice(0, -1).join('/') : null;
      tree.innerHTML =
        (up !== null
          ? `<div class="cm-tree-item dir" data-path="${esc(up)}" data-type="dir">↑ ..</div>`
          : '') +
        entries.map((e) =>
          `<div class="cm-tree-item ${e.type === 'dir' ? 'dir' : ''}" data-path="${esc(e.path)}" data-type="${e.type}">
            ${e.type === 'dir' ? '▸' : '·'} ${esc(e.name)}
          </div>`
        ).join('');
      tree.querySelectorAll('.cm-tree-item').forEach((el) => {
        el.addEventListener('click', async () => {
          if (el.dataset.type === 'dir') await this._loadTree(el.dataset.path);
          else await this._openFile(el.dataset.path);
        });
      });
    } catch (err) {
      tree.innerHTML = `<div class="cm-muted">${esc(err.message)}</div>`;
    }
  }

  async _openFile(path) {
    if (!this.workspaceId) return;
    try {
      if (!this.openFiles.has(path)) {
        const data = await CodingAPI.readFile(this.workspaceId, path);
        this.openFiles.set(path, { content: data.content || '', dirty: false });
      }
      this.activePath = path;
      this._renderTabs();
      this._renderEditor();
      this._log(`Opened ${path}`);
      // Universal Explain: always resolve opened file symbols against Twin
    const base = path.split('/').pop().replace(/\.\w+$/, '');
    if (base) this._explainSymbol(base);
    } catch (err) {
      this._log(`Open failed: ${err.message}`);
    }
  }

  _renderTabs() {
    const tabs = this.root.querySelector('[data-role="tabs"]');
    tabs.innerHTML = [...this.openFiles.keys()].map((p) => {
      const f = this.openFiles.get(p);
      const name = p.split('/').pop() + (f.dirty ? ' •' : '');
      return `<button type="button" class="cm-tab ${p === this.activePath ? 'active' : ''}" data-path="${esc(p)}">${esc(name)}</button>`;
    }).join('');
    tabs.querySelectorAll('.cm-tab').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.activePath = btn.dataset.path;
        this._renderTabs();
        this._renderEditor();
      });
    });
  }

  _renderEditor() {
    const wrap = this.root.querySelector('[data-role="editor-wrap"]');
    if (!this.activePath || !this.openFiles.has(this.activePath)) {
      wrap.innerHTML = `<div class="cm-editor-empty" data-role="empty">Select a workspace file to edit.</div>`;
      return;
    }
    const file = this.openFiles.get(this.activePath);
    const lines = (file.content || '').split('\n');
    const gutter = lines.map((_, i) => i + 1).join('\n');
    wrap.innerHTML = `
      <div class="cm-gutter" data-role="gutter">${esc(gutter)}</div>
      <textarea class="cm-editor ${this.xray ? 'xray-on' : ''}" data-role="editor" spellcheck="false"></textarea>
    `;
    const ta = wrap.querySelector('[data-role="editor"]');
    ta.value = file.content;
    ta.addEventListener('input', () => {
      const f = this.openFiles.get(this.activePath);
      f.content = ta.value;
      f.dirty = true;
      this._renderTabs();
      const g = wrap.querySelector('[data-role="gutter"]');
      if (g) g.textContent = ta.value.split('\n').map((_, i) => i + 1).join('\n');
    });
    ta.addEventListener('mouseup', () => this._onSelect(ta));
    ta.addEventListener('keyup', (e) => {
      if (this.xray) this._scheduleXray(ta);
    });
    ta.addEventListener('click', () => {
      if (this.xray) this._scheduleXray(ta);
    });
    ta.addEventListener('mousemove', (e) => {
      if (!this.xray) return;
      // Approximate word under mouse via caret from coords when available
      if (typeof document.caretRangeFromPoint === 'function' || typeof document.caretPositionFromPoint === 'function') {
        this._scheduleXrayAtPoint(ta, e.clientX, e.clientY);
      }
    });
    ta.addEventListener('mouseleave', () => {
      const tip = this.root.querySelector('[data-role="xray-tip"]');
      if (tip) tip.style.display = 'none';
    });
    // Sync gutter scroll
    ta.addEventListener('scroll', () => {
      const g = wrap.querySelector('[data-role="gutter"]');
      if (g) g.scrollTop = ta.scrollTop;
    });
  }

  _scheduleXray(ta) {
    if (this._xrayTimer) clearTimeout(this._xrayTimer);
    this._xrayTimer = setTimeout(() => this._xrayAtCursor(ta), 80);
  }

  _scheduleXrayAtPoint(ta, clientX, clientY) {
    if (this._xrayTimer) clearTimeout(this._xrayTimer);
    this._xrayTimer = setTimeout(() => {
      let pos = ta.selectionStart;
      try {
        if (document.caretPositionFromPoint) {
          const cp = document.caretPositionFromPoint(clientX, clientY);
          if (cp && cp.offsetNode === ta) pos = cp.offset;
        } else if (document.caretRangeFromPoint) {
          const range = document.caretRangeFromPoint(clientX, clientY);
          if (range) {
            // Textarea often doesn't expose text nodes — fall back to selection
            pos = ta.selectionStart;
          }
        }
      } catch (_) {}
      // Word at cursor for hover path: use nearest identifier around caret
      const left = ta.value.slice(0, pos);
      const right = ta.value.slice(pos);
      const a = left.match(/[\w.]+$/)?.[0] || '';
      const b = right.match(/^[\w.]+/)?.[0] || '';
      const word = (a + b).replace(/^\.+|\.+$/g, '');
      this._showXray(word, clientX, clientY);
    }, 60);
  }

  async _saveActive() {
    if (!this.activePath || !this.workspaceId) return;
    const f = this.openFiles.get(this.activePath);
    if (!f) return;
    try {
      await CodingAPI.writeFile(this.workspaceId, this.activePath, f.content);
      f.dirty = false;
      this._renderTabs();
      this._log(`Saved ${this.activePath} · Semantic Twin notified.`);
      const st = await CodingAPI.status(this.workspaceId);
      this._paintStatus(st);
    } catch (err) {
      this._log(`Save failed: ${err.message}`);
    }
  }

  _onSelect(ta) {
    const sel = ta.value.substring(ta.selectionStart, ta.selectionEnd).trim();
    if (sel && sel.length > 1 && sel.length < 80 && /^[\w.]+$/.test(sel)) {
      // Universal Explain — always Twin-backed when twin is linked
      this._explainSymbol(sel);
    }
  }

  async _xrayAtCursor(ta) {
    const pos = ta.selectionStart;
    const left = ta.value.slice(0, pos);
    const right = ta.value.slice(pos);
    const a = left.match(/[\w.]+$/)?.[0] || '';
    const b = right.match(/^[\w.]+/)?.[0] || '';
    const word = (a + b).replace(/^\.+|\.+$/g, '');
    this._showXray(word);
  }

  /**
   * X-Ray Mode — illuminate Twin relationships at the cursor.
   * Never invents architecture from source alone.
   */
  async _showXray(word, clientX, clientY) {
    const tip = this.root.querySelector('[data-role="xray-tip"]');
    if (!tip) return;
    if (!word || word.length < 2) {
      tip.style.display = 'none';
      return;
    }
    const info = this._lookupSymbol(word);
    if (!info) {
      tip.style.display = 'none';
      return;
    }
    const layer = xrayLayer(info.kind, info.attributes || {});
    const deps = this._neighbors(info.id, 'out').slice(0, 6);
    const dependents = this._neighbors(info.id, 'in').slice(0, 6);
    const relatedApis = this._relatedKinds(info.id, ['api_endpoint', 'route']).slice(0, 4);
    const relatedTables = this._relatedKinds(info.id, ['table', 'column']).slice(0, 4);
    const services = this._relatedKinds(info.id, ['module', 'class', 'function', 'service']).slice(0, 4);

    tip.style.display = 'block';
    if (clientX != null && clientY != null) {
      const wrap = this.root.querySelector('[data-role="editor-wrap"]') || this.root;
      const rect = wrap.getBoundingClientRect();
      tip.style.left = Math.min(rect.width - 220, Math.max(8, clientX - rect.left + 12)) + 'px';
      tip.style.top = Math.min(rect.height - 80, Math.max(8, clientY - rect.top + 12)) + 'px';
    } else {
      tip.style.left = '4rem';
      tip.style.top = '3rem';
    }
    tip.innerHTML = `
      <strong>${esc(info.name)}</strong>
      <span class="cm-xray-kind">${esc(info.kind)}</span>
      <div class="cm-xray-row"><em>Layer</em> ${esc(layer)}</div>
      <div class="cm-xray-row">${esc((info.purpose || info.why_exists || '').slice(0, 140))}</div>
      <div class="cm-xray-row"><em>Upstream</em> ${deps.map((n) => esc(n.name)).join(', ') || '—'}</div>
      <div class="cm-xray-row"><em>Downstream</em> ${dependents.map((n) => esc(n.name)).join(', ') || '—'}</div>
      <div class="cm-xray-row"><em>APIs</em> ${relatedApis.map((n) => esc(n.name)).join(', ') || '—'}</div>
      <div class="cm-xray-row"><em>Tables</em> ${relatedTables.map((n) => esc(n.name)).join(', ') || '—'}</div>
      <div class="cm-xray-row"><em>Services</em> ${services.map((n) => esc(n.name)).join(', ') || '—'}</div>
      <div class="cm-xray-row"><em>Runtime</em> order ${info.execution_order ?? '—'} · ${esc((info.attributes || {}).runtime_owner || 'workspace')}</div>
    `;
  }

  _neighbors(nodeId, direction) {
    if (!this.graphEdges.length || !this.graphById) return [];
    const out = [];
    for (const e of this.graphEdges) {
      if (direction === 'out' && e.source === nodeId) {
        const n = this.graphById.get(e.target);
        if (n) out.push(n);
      }
      if (direction === 'in' && e.target === nodeId) {
        const n = this.graphById.get(e.source);
        if (n) out.push(n);
      }
    }
    // Also use node.dependencies / dependents arrays when present
    const self = this.graphById.get(nodeId);
    if (self && direction === 'out' && (self.dependencies || []).length) {
      for (const id of self.dependencies) {
        const n = this.graphById.get(id);
        if (n && !out.find((x) => x.id === n.id)) out.push(n);
      }
    }
    if (self && direction === 'in' && (self.dependents || []).length) {
      for (const id of self.dependents) {
        const n = this.graphById.get(id);
        if (n && !out.find((x) => x.id === n.id)) out.push(n);
      }
    }
    return out;
  }

  _relatedKinds(nodeId, kinds) {
    const set = new Set(kinds);
    const seen = new Set([nodeId]);
    const result = [];
    let frontier = [nodeId];
    for (let depth = 0; depth < 4 && frontier.length && result.length < 8; depth++) {
      const nextFrontier = [];
      for (const id of frontier) {
        for (const e of this.graphEdges) {
          const next = e.source === id ? e.target : e.target === id ? e.source : null;
          if (!next || seen.has(next)) continue;
          seen.add(next);
          nextFrontier.push(next);
          const n = this.graphById?.get(next);
          if (n && set.has(n.kind)) result.push(n);
        }
      }
      frontier = nextFrontier;
    }
    return result;
  }

  _lookupSymbol(name) {
    if (!this.graphIndex) return null;
    return this.graphIndex.get(name) || this.graphIndex.get(name.toLowerCase()) || null;
  }

  async _indexTwin() {
    if (!this.twinId) return;
    try {
      const g = await CodingAPI.twinGraph(this.twinId);
      const map = new Map();
      const byId = new Map();
      for (const n of g.nodes || []) {
        byId.set(n.id, n);
        map.set(n.name, n);
        map.set((n.name || '').toLowerCase(), n);
        const qn = n.attributes?.qualified_name;
        if (qn) map.set(qn, n);
      }
      this.graphIndex = map;
      this.graphById = byId;
      this.graphEdges = g.edges || [];
    } catch (_) {
      this.graphIndex = null;
      this.graphById = null;
      this.graphEdges = [];
    }
  }

  async _explainSymbol(name) {
    const panel = this.root.querySelector('[data-role="explain"]');
    panel.classList.remove('hidden');
    panel.innerHTML = `<span class="cm-muted">Explaining ${esc(name)}…</span>`;
    if (!this.twinId) {
      panel.innerHTML = `<span class="cm-muted">No Semantic Twin linked. Click “Sync Twin”.</span>`;
      return;
    }
    try {
      const search = await CodingAPI.twinSearch(this.twinId, name);
      const hit = (search.hits || [])[0];
      if (!hit) {
        panel.innerHTML = `<span class="cm-muted">No twin node for “${esc(name)}”.</span>`;
        return;
      }
      const ex = await CodingAPI.twinExplain(this.twinId, hit.node_id, 'intermediate');
      const node = this._lookupSymbol(hit.name) || this.graphById?.get(hit.node_id) || {};
      const c = ex.content || {};
      const layer = xrayLayer(node.kind || hit.kind, node.attributes || {});
      const ups = this._neighbors(hit.node_id, 'out').slice(0, 5).map((n) => n.name).join(', ') || '—';
      const downs = this._neighbors(hit.node_id, 'in').slice(0, 5).map((n) => n.name).join(', ') || '—';
      const apis = this._relatedKinds(hit.node_id, ['api_endpoint', 'route']).slice(0, 4).map((n) => n.name).join(', ') || '—';
      const tables = this._relatedKinds(hit.node_id, ['table', 'column']).slice(0, 4).map((n) => n.name).join(', ') || '—';
      const improves = (node.suggested_improvements || []).slice(0, 3)
        .map((s) => `<div>• ${esc(s.summary || s)}</div>`).join('');
      panel.innerHTML = `
        <h4>${esc(c.title || hit.name)}</h4>
        <p>${esc(c.body || hit.snippet || node.description || '')}</p>
        <ul>
          <li><strong>Kind / layer:</strong> ${esc(hit.kind)} · ${esc(layer)}</li>
          <li><strong>Purpose:</strong> ${esc(node.purpose || '—')}</li>
          <li><strong>Why it exists:</strong> ${esc(node.why_exists || '—')}</li>
          <li><strong>Architectural role:</strong> ${esc(node.purpose || (node.attributes || {}).role || '—')}</li>
          <li><strong>Dependencies:</strong> ${(node.dependencies || []).length} · ${esc(ups)}</li>
          <li><strong>Dependents:</strong> ${(node.dependents || []).length} · ${esc(downs)}</li>
          <li><strong>Related APIs:</strong> ${esc(apis)}</li>
          <li><strong>Database objects:</strong> ${esc(tables)}</li>
          <li><strong>Execution order:</strong> ${node.execution_order ?? '—'}</li>
          <li><strong>Complexity:</strong> ${node.difficulty_score != null ? Number(node.difficulty_score).toFixed(2) : '—'}</li>
          <li><strong>Prompt provenance:</strong> ${esc(node.prompt_id || '—')}</li>
        </ul>
        ${(c.bullets || []).map((b) => `<div>• ${esc(b)}</div>`).join('')}
        ${(c.warnings || []).map((w) => `<div style="color:#fca5a5">⚠ ${esc(w)}</div>`).join('')}
        ${improves ? `<div style="margin-top:0.35rem"><strong>Suggested improvements</strong>${improves}</div>` : ''}
      `;
      this._lastNodeId = hit.node_id;
    } catch (err) {
      panel.innerHTML = `<span class="cm-muted">${esc(err.message)}</span>`;
    }
  }

  async _command(cmd) {
    const selection = this._selection();
    const ctx = this._contextBlurb();
    if (cmd === 'explain') {
      if (selection) await this._explainSymbol(selection);
      else this._assistant('Select a symbol in the editor, then Explain.');
      return;
    }
    if (cmd === 'review' && this.twinId) {
      this._assistant('Running architecture review…');
      try {
        const r = await CodingAPI.review(this.twinId);
        this._assistant(`Review overall **${r.overall}**. Findings: ${(r.findings || []).length}. Top: ${((r.findings || [])[0] || {}).title || 'none'}`);
      } catch (e) {
        this._assistant(`Review failed: ${e.message}`);
      }
      return;
    }
    if (cmd === 'quiz' && this.twinId) {
      try {
        const q = await CodingAPI.twinQuiz(this.twinId);
        const first = (q.questions || [])[0];
        this._assistant(first
          ? `Quiz: ${first.prompt}\n${(first.choices || []).map((c, i) => `${i + 1}. ${c}`).join('\n')}`
          : 'No quiz questions.');
      } catch (e) {
        this._assistant(e.message);
      }
      return;
    }
    if (cmd === 'tutorial' && this.twinId) {
      try {
        const t = await CodingAPI.twinTutorial(this.twinId, this._lastNodeId);
        this._assistant(`Tutorial “${t.title}” — ${(t.steps || []).length} steps.\n` +
          (t.steps || []).slice(0, 4).map((s, i) => `${i + 1}. ${s.title}: ${(s.body || '').slice(0, 100)}`).join('\n'));
      } catch (e) {
        this._assistant(e.message);
      }
      return;
    }
    if (cmd === 'simulate' && this.twinId) {
      const proposal = selection || `Modify ${this.activePath || 'current module'}`;
      try {
        const s = await CodingAPI.twinSimulate(this.twinId, proposal, this._lastNodeId);
        this._assistant(`Simulation risk **${s.risk_level}**. Affected nodes: ${(s.affected_node_ids || []).length}.\n${s.narrative || ''}`);
      } catch (e) {
        this._assistant(e.message);
      }
      return;
    }
    // Generic assistant responses with full context
    const prompts = {
      ask: `As ${this.agent}: answer about ${ctx}`,
      edit: `As ${this.agent}: propose an edit for selection “${selection || '(none)'}” in ${ctx}`,
      refactor: `As ${this.agent}: refactor plan for ${ctx}`,
      generate: `As ${this.agent}: generate code for ${ctx}`,
      test: `As ${this.agent}: tests for ${ctx}`,
      debug: `As ${this.agent}: debug approach for ${ctx}`,
    };
    this._assistant(this._localAssist(cmd, selection, ctx, prompts[cmd] || cmd));
  }

  _localAssist(cmd, selection, ctx, intent) {
    const lines = [
      `**${this.agent}** · ${cmd}`,
      `Context: ${ctx}`,
      selection ? `Selection: \`${selection}\`` : '',
      this.twinId ? `Twin: \`${this.twinId.slice(0, 8)}…\` (use Explain / Review / Simulate for twin-backed answers)` : 'No twin yet — Sync Twin for deep explanations.',
      '',
      intent,
    ].filter(Boolean);
    // If we have twin lookup on selection, enrich
    const n = selection && this._lookupSymbol(selection);
    if (n) {
      lines.push('', `Twin hit: **${n.name}** (${n.kind})`, n.purpose || n.description || '');
    }
    return lines.join('\n');
  }

  _selection() {
    const ta = this.root.querySelector('[data-role="editor"]');
    if (!ta) return '';
    return ta.value.substring(ta.selectionStart, ta.selectionEnd).trim();
  }

  _contextBlurb() {
    return [
      this.manifest?.name || 'workspace',
      this.activePath || 'no-file',
      this.manifest?.active_harness || 'no-harness',
      this.manifest?.active_model || 'no-model',
    ].join(' · ');
  }

  _send() {
    const ta = this.root.querySelector('[data-role="input"]');
    const text = (ta.value || '').trim();
    if (!text) return;
    this._user(text);
    ta.value = '';
    // Prefer twin search for "what is X" patterns
    const m = text.match(/^(?:what is|explain|where is)\s+(.+?)[?.!]?$/i);
    if (m && this.twinId) {
      this._explainSymbol(m[1].trim());
      this._assistant(`Looking up **${m[1].trim()}** in the Semantic Twin…`);
      return;
    }
    this._assistant(this._localAssist('ask', this._selection(), this._contextBlurb(), text));
  }

  _user(text) {
    const chat = this.root.querySelector('[data-role="chat"]');
    chat.insertAdjacentHTML('beforeend',
      `<div class="cm-msg user"><div class="role">You</div><div class="bubble">${esc(text)}</div></div>`);
    chat.scrollTop = chat.scrollHeight;
  }

  _assistant(text) {
    const chat = this.root.querySelector('[data-role="chat"]');
    const html = esc(text).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\n/g, '<br>');
    chat.insertAdjacentHTML('beforeend',
      `<div class="cm-msg assistant"><div class="role">${esc(this.agent)}</div><div class="bubble">${html}</div></div>`);
    chat.scrollTop = chat.scrollHeight;
  }

  _log(msg) {
    const bottom = this.root.querySelector('[data-role="bottom"]');
    const ts = new Date().toLocaleTimeString();
    if (this.bottomTab === 'output' || this.bottomTab === 'logs') {
      bottom.textContent = (bottom.textContent === 'Ready.' ? '' : bottom.textContent + '\n') + `[${ts}] ${msg}`;
      bottom.scrollTop = bottom.scrollHeight;
    }
  }

  _renderBottom() {
    const bottom = this.root.querySelector('[data-role="bottom"]');
    if (this.bottomTab === 'execution') {
      bottom.innerHTML = `<div class="cm-exec-path">${EXEC_STAGES.map((s, i) =>
        `<span class="cm-exec-step" data-step="${i}">${esc(s)}</span>${i < EXEC_STAGES.length - 1 ? '<span class="cm-exec-arrow">→</span>' : ''}`
      ).join('')}</div><div class="cm-muted">Click Execution in the toolbar to animate.</div>`;
      return;
    }
    if (this.bottomTab === 'problems') {
      bottom.textContent = 'No problems reported.';
      return;
    }
    if (this.bottomTab === 'terminal') {
      bottom.textContent = 'Terminal is harness-backed. Start the active harness for full PTY integration.';
      return;
    }
    bottom.textContent = bottom.textContent || 'Ready.';
  }

  async _runExecutionAnimation() {
    this.bottomTab = 'execution';
    this.root.querySelectorAll('[data-bottom]').forEach((b) =>
      b.classList.toggle('active', b.dataset.bottom === 'execution'));
    this._renderBottom();
    let frames = null;
    if (this.twinId) {
      try {
        const viz = await CodingAPI.runtimeViz(this.twinId);
        frames = viz.frames || null;
      } catch (_) {}
    }
    const steps = this.root.querySelectorAll('.cm-exec-step');
    let i = 0;
    if (this._execTimer) clearInterval(this._execTimer);
    this._execTimer = setInterval(() => {
      steps.forEach((el, idx) => el.classList.toggle('active', idx === i));
      const label = frames?.[i]?.label || EXEC_STAGES[i];
      this._log(`Execution: ${label}`);
      i += 1;
      if (i >= steps.length) {
        clearInterval(this._execTimer);
        this._execTimer = null;
      }
    }, 700);
  }

  async _ensureTwin() {
    if (!this.workspaceId) return this._log('Select a workspace first.');
    this._log('Ensuring Semantic Twin…');
    try {
      const m = await CodingAPI.ensureTwin(this.workspaceId);
      this.manifest = m;
      this.twinId = m.twin_id;
      const st = await CodingAPI.status(this.workspaceId);
      this._paintStatus(st);
      await this._indexTwin();
      this._log(`Twin ready: ${m.twin_id || '—'}`);
      this._assistant(`Semantic Twin linked. You can Explain, Review, Quiz, and Simulate.`);
    } catch (err) {
      this._log(`Twin ensure failed: ${err.message}`);
    }
  }

  async _startHarness() {
    if (!this.workspaceId) return this._log('Select a workspace first.');
    this._log('Starting harness…');
    try {
      const res = await CodingAPI.startHarness(this.workspaceId, {
        harness_id: this.manifest?.active_harness || 'opencode',
      });
      this.manifest = res.manifest;
      this._paintStatus({ manifest: this.manifest, twin_status: this.twinId ? 'ready' : 'missing', harness_state: 'active', sync_status: 'live' });
      this._log(`Harness ${res.handle?.harness_id} started (${res.handle?.metadata?.mode || 'ok'}).`);
    } catch (err) {
      this._log(`Harness start: ${err.message}`);
    }
  }

  async _newWorkspace() {
    const name = prompt('Workspace name', 'My Project');
    if (!name) return;
    const root = prompt('Repository root (absolute path)', '');
    if (!root) return;
    try {
      const m = await CodingAPI.createWorkspace({
        name,
        repo_root: root,
        active_harness: 'opencode',
        init_git: true,
      });
      await this._refreshWorkspaces();
      const sel = this.root.querySelector('[data-role="ws-select"]');
      sel.value = m.workspace_id;
      await this._loadWorkspace(m.workspace_id);
    } catch (err) {
      alert(err.message);
    }
  }

  async _setLeft(tab) {
    this.leftTab = tab;
    this.root.querySelectorAll('[data-left]').forEach((b) =>
      b.classList.toggle('active', b.dataset.left === tab));
    const tree = this.root.querySelector('[data-role="tree"]');
    const panel = this.root.querySelector('[data-role="left-panel"]');
    if (tab === 'explorer') {
      panel.classList.add('hidden');
      tree.classList.remove('hidden');
      await this._loadTree('');
      return;
    }
    tree.classList.add('hidden');
    panel.classList.remove('hidden');
    if (tab === 'search') {
      panel.innerHTML = `<input class="cm-ws-select" style="width:100%;margin-bottom:0.4rem" data-role="search-q" placeholder="Search twin / files…"/>
        <div data-role="search-out" class="cm-muted">Enter a query.</div>`;
      panel.querySelector('[data-role="search-q"]').addEventListener('keydown', async (e) => {
        if (e.key !== 'Enter') return;
        const q = e.target.value.trim();
        const out = panel.querySelector('[data-role="search-out"]');
        if (!this.twinId) {
          out.textContent = 'No twin — Sync Twin first.';
          return;
        }
        try {
          const r = await CodingAPI.twinSearch(this.twinId, q);
          out.innerHTML = (r.hits || []).map((h) =>
            `<div class="cm-tree-item" data-nid="${esc(h.node_id)}"><strong>${esc(h.name)}</strong> <span class="cm-muted">${esc(h.kind)}</span><br>${esc(h.snippet || '')}</div>`
          ).join('') || 'No hits.';
          out.querySelectorAll('[data-nid]').forEach((el) => {
            el.addEventListener('click', () => this._explainSymbol(el.querySelector('strong').textContent));
          });
        } catch (err) {
          out.textContent = err.message;
        }
      });
      return;
    }
    if (tab === 'git') {
      panel.innerHTML = `<div class="cm-muted">Branch: <strong>${esc(this.manifest?.branch || '—')}</strong><br>Root: ${esc(this.manifest?.repo_root || '—')}<br>Worktree: ${esc(this.manifest?.worktree || 'default')}</div>`;
      return;
    }
    if (tab === 'twin') {
      panel.innerHTML = `<div class="cm-muted">Twin: ${esc(this.twinId || 'not linked')}<br>
        <button type="button" class="cm-btn" data-act="panel-twin">Open Twin UI</button>
        <button type="button" class="cm-btn" data-act="panel-sync">Sync Twin</button></div>`;
      panel.querySelector('[data-act="panel-twin"]')?.addEventListener('click', () =>
        this.root.querySelector('[data-act="twin-ui"]').click());
      panel.querySelector('[data-act="panel-sync"]')?.addEventListener('click', () => this._ensureTwin());
      return;
    }
    if (tab === 'runtime') {
      panel.innerHTML = `<div class="cm-muted">
        Profile: ${esc(this.manifest?.runtime_profile || 'default')}<br>
        Model: ${esc(this.manifest?.active_model || '—')}<br>
        Endpoint: ${esc(this.manifest?.endpoint_url || 'Spark Runtime')}<br>
        Harness: ${esc(this.manifest?.active_harness || '—')}
      </div>`;
      if (this.twinId) {
        try {
          const viz = await CodingAPI.runtimeViz(this.twinId);
          panel.innerHTML += `<div style="margin-top:0.5rem">${esc(viz.path_label || '')}</div>
            <ol>${(viz.frames || []).slice(0, 8).map((f) => `<li>${esc(f.stage)} — ${esc(f.label)}</li>`).join('')}</ol>`;
        } catch (_) {}
      }
      return;
    }
    if (tab === 'knowledge') {
      panel.innerHTML = `<input class="cm-ws-select" style="width:100%" data-role="k-q" placeholder="Org memory…"/>
        <div data-role="k-out" class="cm-muted" style="margin-top:0.4rem">Search organizational knowledge.</div>`;
      panel.querySelector('[data-role="k-q"]').addEventListener('keydown', async (e) => {
        if (e.key !== 'Enter') return;
        try {
          const r = await CodingAPI.memorySearch(e.target.value);
          panel.querySelector('[data-role="k-out"]').innerHTML =
            (r.hits || []).slice(0, 12).map((h) =>
              `<div><strong>${esc(h.kind)}</strong> ${esc(h.title)}<br><span class="cm-muted">${esc((h.summary || '').slice(0, 100))}</span></div>`
            ).join('') || 'No hits.';
        } catch (err) {
          panel.querySelector('[data-role="k-out"]').textContent = err.message;
        }
      });
      return;
    }
    if (tab === 'terminal') {
      panel.innerHTML = `<div class="cm-muted">Terminal panel — harness PTY when engine is running.<br>Use bottom Terminal tab for session output.</div>`;
    }
  }
}

function setChip(root, key, value) {
  const el = root.querySelector(`[data-chip="${key}"]`);
  if (el) el.innerHTML = `<strong>${key}</strong> ${esc(value)}`;
}

/** Architectural layer for X-Ray overlay — derived from Twin kind, not source. */
function xrayLayer(kind, attrs = {}) {
  if (attrs.architecture_kind) return String(attrs.architecture_kind);
  const map = {
    component: 'frontend', page: 'frontend', route: 'frontend', hook: 'frontend',
    api_endpoint: 'api', middleware: 'api',
    function: 'service', method: 'service', class: 'service', module: 'service',
    table: 'database', column: 'database', migration: 'database',
    event: 'queue', event_handler: 'queue', job: 'job',
    storage: 'storage', external: 'external', security_surface: 'security',
  };
  return map[kind] || kind || 'unknown';
}

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Singleton
let _instance = null;
export function getCodingMode() {
  if (!_instance) _instance = new CodingMode();
  return _instance;
}

export default { getCodingMode, CodingMode };
