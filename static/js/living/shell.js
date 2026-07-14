/**
 * Living Software Workspace shell
 * Mission Control + Architecture + Time Travel + Runtime + Review + Replay + Learning
 * Twin is source of truth. Does not redesign Chat or Coding Mode.
 */
import { LivingAPI } from './api.js';
import { ArchitectureCanvas, layerLegendHtml } from './canvas.js';
import { CommandCenter } from './command-center.js';

const VIEWS = [
  { id: 'mission', label: 'Mission Control' },
  { id: 'architecture', label: 'Architecture' },
  { id: 'timeline', label: 'Time Travel' },
  { id: 'runtime', label: 'Runtime' },
  { id: 'review', label: 'Review' },
  { id: 'replay', label: 'Build Replay' },
  { id: 'learning', label: 'Learning' },
  { id: 'knowledge', label: 'Knowledge' },
];

const REPLAY_STAGES = [
  'Requirements', 'Architecture', 'Database', 'Backend',
  'Frontend', 'Tests', 'Reviews', 'Refactors', 'Current State',
];

export class LivingShell {
  constructor() {
    this.root = null;
    this.view = 'mission';
    this.workspaceId = null;
    this.manifest = null;
    this.twinId = null;
    this.graph = { nodes: [], edges: [] };
    this.selected = null;
    this.canvas = null;
    this.cmd = null;
    this._bound = false;
    this._replayIdx = 0;
    this._replayTimer = null;
  }

  async open(view) {
    this._ensure();
    this.root.classList.add('open');
    document.body.classList.add('living-open');
    if (view) this.view = view;
    await this._refreshContext();
    this._paintNav();
    await this._renderView();
  }

  close() {
    if (this.root) this.root.classList.remove('open');
    document.body.classList.remove('living-open');
    if (this._replayTimer) clearInterval(this._replayTimer);
    if (location.pathname.startsWith('/mission') ||
        location.pathname.startsWith('/architecture') ||
        location.pathname.startsWith('/runtime-viz') ||
        location.pathname.startsWith('/time-travel')) {
      try { history.pushState({}, '', '/'); } catch (_) {}
    }
  }

  isOpen() {
    return !!(this.root && this.root.classList.contains('open'));
  }

  toggle(view) {
    if (this.isOpen() && (!view || view === this.view)) this.close();
    else this.open(view);
  }

  openCommandCenter() {
    this._ensure();
    this.cmd.open();
  }

  _ensure() {
    if (!document.getElementById('living-css')) {
      const l = document.createElement('link');
      l.id = 'living-css';
      l.rel = 'stylesheet';
      l.href = '/static/js/living/styles.css';
      document.head.appendChild(l);
    }
    if (this.root) return;
    this.root = document.createElement('div');
    this.root.id = 'living-root';
    this.root.innerHTML = `
      <div class="lv-top">
        <span class="lv-brand">Living Workspace</span>
        <select class="lv-select" data-role="ws"></select>
        <select class="lv-select" data-role="twin" title="Semantic Twin"></select>
        <nav class="lv-nav" data-role="nav"></nav>
        <div class="lv-actions">
          <button type="button" class="lv-btn" data-act="cmd" title="Command Center (Ctrl+K)">⌘K</button>
          <button type="button" class="lv-btn" data-act="coding">Coding</button>
          <button type="button" class="lv-btn" data-act="twin-ui">Twin Explorer</button>
          <button type="button" class="lv-btn" data-act="refresh">Refresh</button>
          <button type="button" class="lv-btn primary" data-act="close">Close</button>
        </div>
      </div>
      <div class="lv-main">
        <div class="lv-view" data-role="view"></div>
        <aside class="lv-detail" data-role="detail">
          <p class="lv-muted">Select a Twin entity. Explain, dependencies, history, and reviews appear here — from the Semantic Twin.</p>
        </aside>
      </div>
    `;
    document.body.appendChild(this.root);
    this.cmd = new CommandCenter({ onAction: (c) => this._runCommand(c) });
    this._bind();
  }

  _bind() {
    if (this._bound) return;
    this._bound = true;
    const r = this.root;
    r.querySelector('[data-act="close"]').addEventListener('click', () => this.close());
    r.querySelector('[data-act="refresh"]').addEventListener('click', async () => {
      await this._refreshContext(true);
      await this._renderView();
    });
    r.querySelector('[data-act="cmd"]').addEventListener('click', () => this.cmd.open());
    r.querySelector('[data-act="coding"]').addEventListener('click', async () => {
      this.close();
      const { getCodingMode } = await import('../coding/mode.js');
      getCodingMode().open();
    });
    r.querySelector('[data-act="twin-ui"]').addEventListener('click', () => {
      const q = this.twinId ? `?twin=${encodeURIComponent(this.twinId)}` : '';
      window.open(`/semantic-twin${q}`, '_blank');
    });
    r.querySelector('[data-role="ws"]').addEventListener('change', async (e) => {
      this.workspaceId = e.target.value || null;
      if (this.workspaceId) {
        this.manifest = await LivingAPI.workspace(this.workspaceId);
        this.twinId = this.manifest.twin_id || this.twinId;
      }
      await this._loadTwinGraph();
      await this._renderView();
    });
    r.querySelector('[data-role="twin"]').addEventListener('change', async (e) => {
      this.twinId = e.target.value || null;
      await this._loadTwinGraph();
      await this._renderView();
    });

    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        // Global command center when living or coding open, or always
        e.preventDefault();
        this._ensure();
        this.cmd.toggle();
      }
      if (e.key === 'Escape' && this.cmd.el?.classList.contains('open')) {
        this.cmd.close();
      }
    });
  }

  _paintNav() {
    const nav = this.root.querySelector('[data-role="nav"]');
    nav.innerHTML = VIEWS.map((v) =>
      `<button type="button" data-view="${v.id}" class="${v.id === this.view ? 'active' : ''}">${v.label}</button>`
    ).join('');
    nav.querySelectorAll('[data-view]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        this.view = btn.dataset.view;
        this._paintNav();
        this._syncUrl();
        await this._renderView();
      });
    });
  }

  _syncUrl() {
    const map = {
      mission: '/mission',
      architecture: '/architecture',
      timeline: '/time-travel',
      runtime: '/runtime-viz',
      review: '/mission',
      replay: '/mission',
      learning: '/mission',
      knowledge: '/mission',
    };
    const path = map[this.view] || '/mission';
    try { history.pushState({}, '', path); } catch (_) {}
  }

  async _refreshContext(forceTwin) {
    const wsSel = this.root.querySelector('[data-role="ws"]');
    const twinSel = this.root.querySelector('[data-role="twin"]');
    try {
      const ws = await LivingAPI.workspaces();
      const list = ws.workspaces || [];
      wsSel.innerHTML = `<option value="">Workspace…</option>` +
        list.map((w) => `<option value="${esc(w.workspace_id)}">${esc(w.name)}</option>`).join('');
      if (!this.workspaceId && list[0]) this.workspaceId = list[0].workspace_id;
      if (this.workspaceId) {
        wsSel.value = this.workspaceId;
        this.manifest = await LivingAPI.workspace(this.workspaceId);
        if (this.manifest.twin_id) this.twinId = this.manifest.twin_id;
      }
    } catch (e) {
      wsSel.innerHTML = `<option value="">${esc(e.message)}</option>`;
    }
    try {
      const twins = await LivingAPI.listTwins();
      const tlist = twins.twins || [];
      twinSel.innerHTML = `<option value="">Semantic Twin…</option>` +
        tlist.map((t) =>
          `<option value="${esc(t.twin_id)}">${esc(t.meta?.application_name || t.application_id)} r${t.content_revision}</option>`
        ).join('');
      if (!this.twinId && tlist[0]) this.twinId = tlist[0].twin_id;
      if (this.twinId) twinSel.value = this.twinId;
    } catch (e) {
      twinSel.innerHTML = `<option value="">${esc(e.message)}</option>`;
    }
    if (this.twinId && (forceTwin || !this.graph.nodes.length)) {
      await this._loadTwinGraph();
    }
  }

  async _loadTwinGraph() {
    if (!this.twinId) {
      this.graph = { nodes: [], edges: [] };
      return;
    }
    try {
      this.graph = await LivingAPI.graph(this.twinId);
    } catch (e) {
      this.graph = { nodes: [], edges: [] };
      this._detail(`<p class="lv-muted">Twin load failed: ${esc(e.message)}</p>`);
    }
  }

  async _renderView() {
    const view = this.root.querySelector('[data-role="view"]');
    if (!this.twinId && this.view !== 'mission') {
      view.innerHTML = `<p class="lv-muted">Link a workspace twin (Mission Control → Ensure Twin) or select a Twin above.</p>`;
      return;
    }
    switch (this.view) {
      case 'mission': await this._viewMission(view); break;
      case 'architecture': await this._viewArchitecture(view); break;
      case 'timeline': await this._viewTimeline(view); break;
      case 'runtime': await this._viewRuntime(view); break;
      case 'review': await this._viewReview(view); break;
      case 'replay': await this._viewReplay(view); break;
      case 'learning': await this._viewLearning(view); break;
      case 'knowledge': await this._viewKnowledge(view); break;
      default: view.innerHTML = '';
    }
  }

  // ── 10. Mission Control ──────────────────────────────────────────

  async _viewMission(view) {
    let st = {};
    if (this.workspaceId) {
      try { st = await LivingAPI.workspaceStatus(this.workspaceId); } catch (_) {}
    }
    const m = st.manifest || this.manifest || {};
    const nodes = this.graph.nodes || [];
    const kinds = countBy(nodes, (n) => n.kind);
    let engines = [];
    try { engines = (await LivingAPI.engines()).engines || []; } catch (_) {}

    view.innerHTML = `
      <h2 style="margin:0 0 0.75rem;font-size:1.1rem">Mission Control</h2>
      <p class="lv-muted" style="margin-bottom:0.85rem">All views stay synchronized around the Workspace Manager. Semantic Twin is the source of truth.</p>
      <div class="lv-mission">
        ${card('Workspace', m.name || '—', m.repo_root || '', 'mission-ws')}
        ${card('Active Harness', m.active_harness || st.harness_state || '—', engines.map((e) => e.display_name || e.harness_id).join(', ') || 'register engines', 'mission-harness')}
        ${card('Runtime', m.runtime_profile || 'default', m.endpoint_url || 'Spark Runtime', 'runtime')}
        ${card('Active Model', m.active_model || '—', 'from workspace manifest')}
        ${card('Semantic Twin', st.twin_status || (this.twinId ? 'linked' : 'missing'), this.twinId ? shortId(this.twinId) : 'Ensure Twin', 'architecture')}
        ${card('Architecture', `${nodes.length} nodes`, `${(this.graph.edges || []).length} edges · live`, 'architecture')}
        ${card('Agents', (m.active_agents || []).join(', ') || '—', 'multi-agent regions', 'mission-agents')}
        ${card('Knowledge Memory', m.knowledge_memory_id || 'org', 'org memory', 'knowledge')}
        ${card('Git', m.branch || '—', m.worktree || 'default worktree')}
        ${card('Sync', st.sync_status || '—', 'file changes → twin', 'timeline')}
        ${card('Kinds', Object.keys(kinds).length + ' kinds', Object.entries(kinds).slice(0, 4).map(([k, v]) => `${k}:${v}`).join(' · '))}
        ${card('Active Tasks', '—', 'use Tasks tool for scheduler')}
      </div>
      <div style="margin-top:1rem;display:flex;gap:0.4rem;flex-wrap:wrap">
        <button type="button" class="lv-btn primary" data-m="ensure">Ensure Twin</button>
        <button type="button" class="lv-btn" data-m="arch">Architecture</button>
        <button type="button" class="lv-btn" data-m="review">Review</button>
        <button type="button" class="lv-btn" data-m="runtime">Runtime</button>
        <button type="button" class="lv-btn" data-m="cmd">Command Center</button>
      </div>
    `;
    view.querySelectorAll('.lv-card.clickable').forEach((el) => {
      el.addEventListener('click', () => {
        const v = el.dataset.go;
        if (v && !v.startsWith('mission')) {
          this.view = v;
          this._paintNav();
          this._renderView();
        }
      });
    });
    view.querySelector('[data-m="ensure"]')?.addEventListener('click', async () => {
      if (!this.workspaceId) return alert('Select a workspace');
      const m2 = await LivingAPI.ensureTwin(this.workspaceId);
      this.twinId = m2.twin_id;
      await this._refreshContext(true);
      await this._renderView();
    });
    view.querySelector('[data-m="arch"]')?.addEventListener('click', () => { this.view = 'architecture'; this._paintNav(); this._renderView(); });
    view.querySelector('[data-m="review"]')?.addEventListener('click', () => { this.view = 'review'; this._paintNav(); this._renderView(); });
    view.querySelector('[data-m="runtime"]')?.addEventListener('click', () => { this.view = 'runtime'; this._paintNav(); this._renderView(); });
    view.querySelector('[data-m="cmd"]')?.addEventListener('click', () => this.cmd.open());
    this._detail(missionDetailHtml(m, st, this.twinId, engines));
  }

  // ── 1. Live Architecture Canvas ──────────────────────────────────

  async _viewArchitecture(view) {
    view.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem">
        <h2 style="margin:0;font-size:1.05rem">Live Architecture</h2>
        <span class="lv-muted">Every node is a Semantic Twin entity · auto-updates with code</span>
      </div>
      <div class="lv-canvas-wrap">
        <canvas class="lv-canvas" data-role="canvas"></canvas>
        <div class="lv-legend">${layerLegendHtml()}</div>
      </div>
    `;
    const canvas = view.querySelector('[data-role="canvas"]');
    this.canvas = new ArchitectureCanvas(canvas, {
      onSelect: (n) => this._selectNode(n),
    });
    this.canvas.setGraph(this.graph.nodes || [], this.graph.edges || []);
    requestAnimationFrame(() => this.canvas.resize());
    window.addEventListener('resize', () => this.canvas?.resize(), { once: true });
  }

  // ── 2. Time Travel ───────────────────────────────────────────────

  async _viewTimeline(view) {
    if (!this.twinId) {
      view.innerHTML = `<p class="lv-muted">Select a twin.</p>`;
      return;
    }
    let hist = { versions: [] };
    try { hist = await LivingAPI.timeline(this.twinId); } catch (e) {
      view.innerHTML = `<p class="lv-muted">${esc(e.message)}</p>`;
      return;
    }
    const versions = hist.versions || [];
    view.innerHTML = `
      <h2 style="margin:0 0 0.5rem;font-size:1.05rem">Time Travel</h2>
      <p class="lv-muted">Each checkpoint: code revision · twin graph · architecture · reviews · simulations · prompts.</p>
      <div class="lv-timeline">
        ${versions.length ? versions.slice().reverse().map((v) => `
          <div class="lv-checkpoint" data-rev="${v.revision}">
            <div class="rev">r${v.revision}</div>
            <div>
              <div><strong>${esc(v.label || v.trigger || 'checkpoint')}</strong></div>
              <div class="lv-muted">${esc(v.trigger || '')} · nodes ${v.node_count ?? '—'} · edges ${v.edge_count ?? '—'}</div>
            </div>
            <button type="button" class="lv-btn" data-scrub="${v.revision}">Scrub</button>
          </div>
        `).join('') : `<p class="lv-muted">No checkpoints yet. Generate/update a twin to create history.</p>`}
      </div>
    `;
    view.querySelectorAll('[data-scrub]').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const rev = Number(btn.dataset.scrub);
        try {
          const scrub = await LivingAPI.scrub(this.twinId, rev);
          this._detail(scrubHtml(scrub));
          view.querySelectorAll('.lv-checkpoint').forEach((c) =>
            c.classList.toggle('active', Number(c.dataset.rev) === rev));
        } catch (err) {
          this._detail(`<p class="lv-muted">${esc(err.message)}</p>`);
        }
      });
    });
  }

  // ── 3. Runtime Visualization ─────────────────────────────────────

  async _viewRuntime(view) {
    let viz = { frames: [], bottlenecks: [], failures: [], recent_events: [] };
    if (this.twinId) {
      try { viz = await LivingAPI.runtimeViz(this.twinId); } catch (_) {}
    }
    const m = this.manifest || {};
    // Observable metrics: twin topology + workspace + optional host telemetry
    const nodes = this.graph.nodes || [];
    const asyncN = nodes.filter((n) => (n.attributes || {}).async).length;
    const apis = nodes.filter((n) => n.kind === 'api_endpoint').length;
    const hot = nodes.filter((n) => n.difficulty_score >= 0.65).length;
    const tel = await loadRuntimeTelemetry(m);
    const stage = (viz.frames || [])[0]?.label || 'idle';
    const lat = tel.latency_ms != null ? `${tel.latency_ms} ms` : (viz.bottlenecks?.[0]?.duration_ms ? `${viz.bottlenecks[0].duration_ms} ms` : '—');
    const tps = tel.throughput != null ? String(tel.throughput) : (tel.average_tps != null ? String(tel.average_tps) : '—');
    view.innerHTML = `
      <h2 style="margin:0 0 0.5rem;font-size:1.05rem">Runtime Digital Twin</h2>
      <p class="lv-muted">Inference and execution become observable — not hidden.</p>
      <div class="lv-metrics">
        ${metric(m.active_model || tel.model || '—', 'Active model')}
        ${metric(m.runtime_profile || tel.strategy || 'default', 'Execution strategy')}
        ${metric(tel.vram || '—', 'VRAM usage')}
        ${metric(tel.ram || '—', 'RAM usage')}
        ${metric(tel.ssd || 'SSD stream', 'SSD streaming')}
        ${metric(tel.cache || '—', 'Cache activity')}
        ${metric(stage, 'Current stage')}
        ${metric(tel.prediction || '—', 'Prediction accuracy')}
        ${metric(tps, 'Throughput')}
        ${metric(lat, 'Latency')}
        ${metric(String((viz.bottlenecks || []).length), 'Bottlenecks')}
        ${metric(String((viz.failures || []).length), 'Failures')}
      </div>
      <h4 class="lv-muted" style="margin:0.5rem 0">Execution path</h4>
      <div class="lv-stages" data-role="stages">
        ${(viz.frames || defaultFrames()).map((f, i) =>
          `<span class="lv-stage ${f.highlight === 'failure' ? 'fail' : f.highlight === 'slow' ? 'slow' : ''}" data-i="${i}">${esc(f.label || f.stage)}</span>${i < (viz.frames || defaultFrames()).length - 1 ? '<span class="lv-arrow">→</span>' : ''}`
        ).join('')}
      </div>
      <div style="margin-top:0.75rem;display:flex;gap:0.4rem;flex-wrap:wrap">
        <button type="button" class="lv-btn primary" data-act="animate">Replay execution</button>
        <button type="button" class="lv-btn" data-act="refresh-rt">Refresh telemetry</button>
      </div>
      <p class="lv-muted" style="margin-top:0.75rem">${esc(viz.path_label || '')}</p>
      <p class="lv-muted">Twin surfaces: ${apis} APIs · ${asyncN} async · ${hot} hot/complex</p>
    `;
    view.querySelector('[data-act="animate"]')?.addEventListener('click', () => {
      const stages = view.querySelectorAll('.lv-stage');
      let i = 0;
      const t = setInterval(() => {
        stages.forEach((el, idx) => el.classList.toggle('active', idx === i));
        i += 1;
        if (i >= stages.length) clearInterval(t);
      }, 650);
    });
    view.querySelector('[data-act="refresh-rt"]')?.addEventListener('click', () => this._viewRuntime(view));
    this._detail(`
      <h3>Runtime metadata</h3>
      <p class="lv-muted">Twin execution path + workspace harness telemetry. Hardware counters fill when Runtime Manager / host reports them.</p>
      <ul>
        <li>Model: ${esc(m.active_model || tel.model || '—')}</li>
        <li>Profile: ${esc(m.runtime_profile || 'default')}</li>
        <li>Endpoint: ${esc(m.endpoint_url || 'Spark Runtime default')}</li>
        <li>Harness: ${esc(m.active_harness || '—')}</li>
        <li>Memory tier: ${esc(tel.memory_tier || '—')}</li>
        <li>Cache hit rate: ${esc(tel.cache_hit_rate != null ? String(tel.cache_hit_rate) : '—')}</li>
        <li>Recent events: ${(viz.recent_events || []).length}</li>
      </ul>
    `);
  }

  // ── 6. Architecture Review ───────────────────────────────────────

  async _viewReview(view) {
    view.innerHTML = `
      <h2 style="margin:0 0 0.5rem;font-size:1.05rem">Architecture Review</h2>
      <p class="lv-muted">Findings attach to Twin nodes. Click a finding to open its entity.</p>
      <button type="button" class="lv-btn primary" data-act="run-review">Run review</button>
      <div data-role="review-out" style="margin-top:0.75rem"></div>
    `;
    view.querySelector('[data-act="run-review"]').addEventListener('click', async () => {
      const out = view.querySelector('[data-role="review-out"]');
      out.innerHTML = `<span class="lv-muted">Analyzing twin…</span>`;
      try {
        const r = await LivingAPI.review(this.twinId);
        out.innerHTML = `
          <p>Overall <strong>${r.overall}</strong></p>
          <div>${Object.entries(r.scores || {}).map(([k, v]) =>
            `<span class="lv-chip">${esc(k)}: ${v}</span>`).join('')}</div>
          <div style="margin-top:0.65rem">
            ${(r.findings || []).map((f) => `
              <div class="lv-finding" data-nodes="${esc((f.node_ids || []).join(','))}">
                <span class="sev sev-${esc(f.severity)}">${esc(f.severity)}</span>
                <strong>${esc(f.title)}</strong>
                <div class="lv-muted">${esc(f.explanation)}</div>
                <div class="lv-muted">Fix: ${esc(f.proposed_solution || '')}</div>
              </div>
            `).join('') || '<p class="lv-muted">No findings.</p>'}
          </div>
        `;
        out.querySelectorAll('.lv-finding').forEach((el) => {
          el.addEventListener('click', () => {
            const id = (el.dataset.nodes || '').split(',').filter(Boolean)[0];
            if (!id) return;
            const n = (this.graph.nodes || []).find((x) => x.id === id);
            if (n) this._selectNode(n);
          });
        });
        await this._loadTwinGraph(); // refresh attached findings
      } catch (e) {
        out.innerHTML = `<p class="lv-muted">${esc(e.message)}</p>`;
      }
    });
  }

  // ── 7. Build Replay ──────────────────────────────────────────────

  async _viewReplay(view) {
    const nodes = this.graph.nodes || [];
    const counts = {
      Requirements: nodes.filter((n) => n.kind === 'requirement').length,
      Architecture: nodes.filter((n) => (n.attributes || {}).architecture_id || n.kind === 'design_decision').length,
      Database: nodes.filter((n) => n.kind === 'table' || n.kind === 'column').length,
      Backend: nodes.filter((n) => ['function', 'method', 'class', 'module', 'api_endpoint'].includes(n.kind)).length,
      Frontend: nodes.filter((n) => ['component', 'page', 'hook', 'route'].includes(n.kind)).length,
      Tests: nodes.filter((n) => n.kind === 'test').length,
      Reviews: nodes.filter((n) => n.kind === 'pattern' && (n.attributes || {}).review_id).length,
      Refactors: (this.manifest?.metadata?.last_refactor ? 1 : 0),
      'Current State': nodes.length,
    };
    view.innerHTML = `
      <h2 style="margin:0 0 0.5rem;font-size:1.05rem">Build Replay</h2>
      <p class="lv-muted">Replay how the application evolved — from requirements to current state.</p>
      <div class="lv-replay" data-role="replay">
        ${REPLAY_STAGES.map((s, i) =>
          `<span class="lv-replay-step" data-i="${i}">${esc(s)} <small>(${counts[s] ?? 0})</small></span>${i < REPLAY_STAGES.length - 1 ? '<span class="lv-arrow">→</span>' : ''}`
        ).join('')}
      </div>
      <button type="button" class="lv-btn primary" data-act="play-replay">Play evolution</button>
      <div data-role="replay-body" class="lv-muted" style="margin-top:0.75rem"></div>
    `;
    const body = view.querySelector('[data-role="replay-body"]');
    const steps = view.querySelectorAll('.lv-replay-step');
    const show = (i) => {
      steps.forEach((el, idx) => {
        el.classList.toggle('active', idx === i);
        el.classList.toggle('done', idx < i);
      });
      const stage = REPLAY_STAGES[i];
      const related = filterStageNodes(nodes, stage);
      body.innerHTML = `<strong>${esc(stage)}</strong> — ${related.length} twin entities<br>` +
        related.slice(0, 12).map((n) => `· ${esc(n.name)} <span class="lv-muted">(${esc(n.kind)})</span>`).join('<br>');
      if (related[0]) this._selectNode(related[0]);
    };
    steps.forEach((el) => el.addEventListener('click', () => show(Number(el.dataset.i))));
    view.querySelector('[data-act="play-replay"]').addEventListener('click', () => {
      let i = 0;
      if (this._replayTimer) clearInterval(this._replayTimer);
      this._replayTimer = setInterval(() => {
        show(i);
        i += 1;
        if (i >= REPLAY_STAGES.length) clearInterval(this._replayTimer);
      }, 900);
    });
    show(0);
  }

  // ── 9. Interactive Learning ──────────────────────────────────────

  async _viewLearning(view) {
    view.innerHTML = `
      <h2 style="margin:0 0 0.5rem;font-size:1.05rem">Interactive Learning</h2>
      <p class="lv-muted">Select a component on Architecture or pick a symbol. Learning uses Twin relationships — not static docs.</p>
      <div class="lv-learn-grid">
        <div class="lv-card">
          <h4>Focus</h4>
          <input class="lv-select" style="width:100%;max-width:none" data-role="learn-q" placeholder="Symbol or concept…" />
          <div style="margin-top:0.5rem;display:flex;flex-wrap:wrap;gap:0.3rem">
            <button type="button" class="lv-btn" data-l="explain">Explain</button>
            <button type="button" class="lv-btn" data-l="exec">Animate execution</button>
            <button type="button" class="lv-btn" data-l="tutorial">Tutorial</button>
            <button type="button" class="lv-btn" data-l="quiz">Quiz</button>
            <button type="button" class="lv-btn" data-l="simulate">Simulate change</button>
          </div>
        </div>
        <div class="lv-card">
          <h4>Safe experiment</h4>
          <textarea class="lv-select" data-role="sim-p" style="width:100%;max-width:none;min-height:4rem;font:inherit" placeholder="What if we split auth into a service?"></textarea>
          <button type="button" class="lv-btn primary" style="margin-top:0.4rem" data-l="sim-run">Simulate (no code changes)</button>
        </div>
      </div>
      <div data-role="learn-out" style="margin-top:0.75rem"></div>
    `;
    const out = view.querySelector('[data-role="learn-out"]');
    const q = () => view.querySelector('[data-role="learn-q"]').value.trim() || this.selected?.name || '';

    view.querySelector('[data-l="explain"]').addEventListener('click', async () => {
      const name = q();
      if (!name) return;
      const hits = await LivingAPI.search(this.twinId, name);
      const hit = (hits.hits || [])[0];
      if (!hit) { out.textContent = 'No twin match.'; return; }
      const n = (this.graph.nodes || []).find((x) => x.id === hit.node_id);
      if (n) this._selectNode(n);
      else await this._selectNodeById(hit.node_id);
    });
    view.querySelector('[data-l="tutorial"]').addEventListener('click', async () => {
      const t = await LivingAPI.tutorial(this.twinId, this.selected?.id);
      out.innerHTML = `<strong>${esc(t.title)}</strong><ol>${(t.steps || []).map((s) =>
        `<li><strong>${esc(s.title)}</strong> — ${esc((s.body || '').slice(0, 160))}</li>`).join('')}</ol>`;
    });
    view.querySelector('[data-l="quiz"]').addEventListener('click', async () => {
      const quiz = await LivingAPI.quiz(this.twinId, this.selected ? [this.selected.id] : null);
      const first = (quiz.questions || [])[0];
      out.innerHTML = first
        ? `<strong>${esc(first.prompt)}</strong><ol>${(first.choices || []).map((c) => `<li>${esc(c)}</li>`).join('')}</ol>
           <p class="lv-muted">${esc(first.explanation || '')}</p>`
        : 'No questions.';
    });
    view.querySelector('[data-l="exec"]').addEventListener('click', async () => {
      if (!this.selected) { out.textContent = 'Select a node first.'; return; }
      const tr = await LivingAPI.traceExec(this.twinId, this.selected.id);
      out.innerHTML = `<div class="lv-stages">${(tr.steps || []).map((s) =>
        `<span class="lv-stage">${esc(s.name)}</span>`).join('<span class="lv-arrow">→</span>')}</div>`;
      this.canvas?.setHighlight((tr.steps || []).map((s) => s.node_id));
    });
    const sim = async () => {
      const proposal = view.querySelector('[data-role="sim-p"]').value.trim() || `Modify ${q()}`;
      const s = await LivingAPI.simulate(this.twinId, proposal, this.selected?.id);
      out.innerHTML = `<strong>Risk ${esc(s.risk_level)}</strong><pre style="white-space:pre-wrap;font-size:0.75rem">${esc(s.narrative || '')}</pre>
        <p class="lv-muted">Affected: ${(s.affected_node_ids || []).length} · effort ~${s.estimated_effort_days}d</p>`;
      this.canvas?.setHighlight(s.affected_node_ids || []);
    };
    view.querySelector('[data-l="simulate"]').addEventListener('click', sim);
    view.querySelector('[data-l="sim-run"]').addEventListener('click', sim);
  }

  // ── Knowledge ────────────────────────────────────────────────────

  async _viewKnowledge(view) {
    view.innerHTML = `
      <h2 style="margin:0 0 0.5rem;font-size:1.05rem">Knowledge Memory</h2>
      <input class="lv-select" style="width:min(28rem,100%);max-width:none" data-role="kq" placeholder="Search org memory…" />
      <div data-role="kout" style="margin-top:0.75rem"></div>
    `;
    view.querySelector('[data-role="kq"]').addEventListener('keydown', async (e) => {
      if (e.key !== 'Enter') return;
      const r = await LivingAPI.memory(e.target.value);
      view.querySelector('[data-role="kout"]').innerHTML =
        (r.hits || []).map((h) =>
          `<div class="lv-card" style="margin-bottom:0.4rem"><strong>${esc(h.kind)}</strong> ${esc(h.title)}
           <div class="sub">${esc(h.summary || '')}</div></div>`
        ).join('') || '<p class="lv-muted">No hits.</p>';
    });
  }

  // ── Universal explain detail ─────────────────────────────────────

  async _selectNode(n) {
    this.selected = n;
    this.canvas?.setSelection(n.id);
    await this._renderExplain(n);
  }

  async _selectNodeById(id) {
    try {
      const n = await LivingAPI.node(this.twinId, id);
      this.selected = n;
      await this._renderExplain(n);
    } catch (e) {
      this._detail(`<p class="lv-muted">${esc(e.message)}</p>`);
    }
  }

  async _renderExplain(n) {
    let explain = {};
    let deps = {};
    let story = {};
    try { explain = await LivingAPI.explain(this.twinId, n.id, 'senior'); } catch (_) {}
    try { deps = await LivingAPI.traceDep(this.twinId, n.id, 'both'); } catch (_) {}
    try { story = await LivingAPI.story(this.twinId, n.id); } catch (_) {}
    const c = explain.content || {};
    const depNodes = (deps.nodes || []).map((id) => (this.graph.nodes || []).find((x) => x.id === id)).filter(Boolean);
    this.canvas?.setHighlight(deps.nodes || [n.id]);

    let source = '';
    if (n.source_file && this.workspaceId) {
      try {
        const f = await LivingAPI.file(this.workspaceId, n.source_file);
        const loc = n.source_location;
        let text = f.content || '';
        if (loc?.start_line) {
          const lines = text.split('\n');
          text = lines.slice(Math.max(0, loc.start_line - 1), loc.end_line || loc.start_line + 20).join('\n');
        } else {
          text = text.slice(0, 800);
        }
        source = `<h4>Source</h4><pre style="font-size:0.7rem;white-space:pre-wrap;max-height:10rem;overflow:auto">${esc(text)}</pre>`;
      } catch (_) {
        source = `<h4>Source</h4><p class="lv-muted">${esc(n.source_file || '—')}</p>`;
      }
    }

    this._detail(`
      <h3>${esc(n.name)}</h3>
      <span class="lv-chip">${esc(n.kind)}</span>
      <span class="lv-chip">diff ${n.difficulty_score != null ? Number(n.difficulty_score).toFixed(2) : '—'}</span>
      <h4>What is this?</h4>
      <p>${esc(c.body || n.description || n.purpose || '')}</p>
      <h4>Why does it exist?</h4>
      <p>${esc(n.why_exists || '—')}</p>
      <h4>Architectural role</h4>
      <p>${esc(n.purpose || '—')}</p>
      <h4>Dependencies · Dependents</h4>
      <p class="lv-muted">deps ${(n.dependencies || []).length} · dependents ${(n.dependents || []).length} · graph walk ${(deps.nodes || []).length}</p>
      <div>${depNodes.slice(0, 12).map((d) => `<span class="lv-chip">${esc(d.name)}</span>`).join('')}</div>
      <h4>Execution</h4>
      <p class="lv-muted">order ${n.execution_order ?? '—'} · story steps ${(story.steps || []).length}</p>
      <h4>Prompt provenance</h4>
      <p class="lv-muted">${esc(n.prompt_id || 'inferred / none')}</p>
      <h4>Improvements</h4>
      <ul>${(n.suggested_improvements || []).slice(0, 5).map((s) =>
        `<li>${esc(s.summary || s)}</li>`).join('') || '<li class="lv-muted">None recorded</li>'}</ul>
      <h4>Security / complexity</h4>
      <p class="lv-muted">${esc((c.warnings || []).join(' · ') || 'See Security viewing mode on twin')}</p>
      ${source}
      <div style="margin-top:0.6rem;display:flex;flex-wrap:wrap;gap:0.3rem">
        <button type="button" class="lv-btn" data-x="exec">Trace execution</button>
        <button type="button" class="lv-btn" data-x="sim">Simulate change</button>
        <button type="button" class="lv-btn" data-x="learn">Teach this</button>
      </div>
    `);
    const d = this.root.querySelector('[data-role="detail"]');
    d.querySelector('[data-x="exec"]')?.addEventListener('click', async () => {
      const tr = await LivingAPI.traceExec(this.twinId, n.id);
      this.canvas?.setHighlight((tr.steps || []).map((s) => s.node_id));
      this._detailExtra(d, `<h4>Execution path</h4><div class="lv-stages">${(tr.steps || []).map((s) =>
        `<span class="lv-stage active">${esc(s.name)}</span>`).join('<span class="lv-arrow">→</span>')}</div>`);
    });
    d.querySelector('[data-x="sim"]')?.addEventListener('click', async () => {
      const s = await LivingAPI.simulate(this.twinId, `Change ${n.name}`, n.id);
      this.canvas?.setHighlight(s.affected_node_ids || []);
      this._detailExtra(d, `<h4>What if I change it?</h4><p>Risk <strong>${esc(s.risk_level)}</strong></p><p class="lv-muted">${esc(s.narrative || '')}</p>`);
    });
    d.querySelector('[data-x="learn"]')?.addEventListener('click', () => {
      this.view = 'learning';
      this._paintNav();
      this._renderView();
    });
  }

  _detailExtra(d, html) {
    const box = document.createElement('div');
    box.innerHTML = html;
    d.appendChild(box);
  }

  _detail(html) {
    this.root.querySelector('[data-role="detail"]').innerHTML = html;
  }

  async _runCommand(cmd) {
    if (cmd.view) {
      this.open(cmd.view);
      return;
    }
    if (cmd.id === 'coding') {
      this.close();
      const { getCodingMode } = await import('../coding/mode.js');
      getCodingMode().open();
      return;
    }
    if (cmd.id === 'twin') {
      window.open(`/semantic-twin${this.twinId ? `?twin=${this.twinId}` : ''}`, '_blank');
      return;
    }
    if (cmd.id === 'explain') {
      if (this.selected) await this._renderExplain(this.selected);
      else {
        this.open('architecture');
        this._detail('<p class="lv-muted">Select a node on the Architecture canvas to Explain.</p>');
      }
      return;
    }
    if (cmd.id === 'review') this.open('review');
    if (cmd.id === 'simulate') this.open('learning');
    if (cmd.id === 'deadcode') {
      await this.open('architecture');
      const dead = (this.graph.nodes || []).filter((n) =>
        ['function', 'component', 'class'].includes(n.kind) && !(n.dependents || []).length
      ).slice(0, 30);
      this.canvas?.setHighlight(dead.map((n) => n.id));
      this._detail(`<h3>Possible dead code</h3><p class="lv-muted">Low/no dependents (twin heuristic)</p>
        ${dead.map((n) => `<div class="lv-chip">${esc(n.name)}</div>`).join('') || 'None flagged'}`);
    }
  }
}

function card(title, val, sub, go) {
  return `<div class="lv-card ${go ? 'clickable' : ''}" ${go ? `data-go="${go}"` : ''}>
    <h4>${esc(title)}</h4>
    <div class="val">${esc(val)}</div>
    <div class="sub">${esc(sub || '')}</div>
  </div>`;
}
function metric(n, l) {
  return `<div class="lv-metric"><div class="n">${esc(n)}</div><div class="l">${esc(l)}</div></div>`;
}
function missionDetailHtml(m, st, twinId, engines) {
  return `<h3>Workspace pulse</h3>
    <p class="lv-muted">Everything below is synchronized through the Workspace Manifest + Semantic Twin.</p>
    <ul>
      <li>ID: ${esc(m.workspace_id || '—')}</li>
      <li>Twin: ${esc(twinId || st.twin_status || '—')}</li>
      <li>Harness engines: ${esc(engines.map((e) => e.harness_id).join(', ') || '—')}</li>
    </ul>`;
}
function scrubHtml(s) {
  return `<h3>Checkpoint r${esc(s.revision)}</h3>
    <h4>Why</h4><p>${esc(s.why || '')}</p>
    <h4>Who</h4><p>${esc(s.who || '')}</p>
    <h4>What changed</h4><pre style="font-size:0.72rem;white-space:pre-wrap">${esc(JSON.stringify(s.what_changed || {}, null, 2))}</pre>
    <h4>Impact</h4><pre style="font-size:0.72rem;white-space:pre-wrap">${esc(JSON.stringify(s.impact || {}, null, 2))}</pre>
    <p class="lv-muted">${esc(s.narrative || '')}</p>`;
}
function defaultFrames() {
  return ['User', 'Frontend', 'State', 'API', 'Logic', 'DB', 'Response', 'UI'].map((s) => ({ stage: s, label: s }));
}

/** Best-effort host / harness telemetry for Runtime Digital Twin. */
async function loadRuntimeTelemetry(manifest = {}) {
  const out = {
    model: manifest.active_model,
    strategy: manifest.runtime_profile,
    vram: null,
    ram: null,
    ssd: 'NVMe stream',
    cache: null,
    prediction: null,
    throughput: null,
    average_tps: null,
    latency_ms: null,
    memory_tier: null,
    cache_hit_rate: null,
  };
  try {
    const r = await fetch('/api/runtime', { credentials: 'same-origin' });
    if (r.ok) {
      const j = await r.json();
      if (j.vram_gb != null) out.vram = `${j.vram_gb} GB`;
      if (j.ram_gb != null) out.ram = `${j.ram_gb} GB`;
      if (j.cache_hit_rate != null) {
        out.cache_hit_rate = j.cache_hit_rate;
        out.cache = `${Math.round(Number(j.cache_hit_rate) * 100)}% hits`;
      }
      if (j.average_tps != null) out.average_tps = j.average_tps;
      if (j.throughput != null) out.throughput = j.throughput;
      if (j.latency_ms != null) out.latency_ms = j.latency_ms;
      if (j.memory_tier) out.memory_tier = j.memory_tier;
      if (j.prediction_accuracy != null) out.prediction = `${Math.round(Number(j.prediction_accuracy) * 100)}%`;
      if (j.active_model) out.model = j.active_model;
    }
  } catch (_) {}
  // Workspace status may carry harness-reported counters
  try {
    if (manifest.telemetry) {
      const t = manifest.telemetry;
      if (t.vram) out.vram = t.vram;
      if (t.ram) out.ram = t.ram;
      if (t.cache) out.cache = t.cache;
    }
  } catch (_) {}
  if (!out.vram) out.vram = 'n/a';
  if (!out.ram) out.ram = 'n/a';
  if (!out.cache) out.cache = out.cache_hit_rate != null ? `${out.cache_hit_rate}` : 'warming';
  if (!out.prediction) out.prediction = 'n/a';
  return out;
}
function filterStageNodes(nodes, stage) {
  const map = {
    Requirements: (n) => n.kind === 'requirement' || n.kind === 'prompt',
    Architecture: (n) => n.kind === 'design_decision' || n.kind === 'application' || (n.attributes || {}).architecture_id,
    Database: (n) => n.kind === 'table' || n.kind === 'column',
    Backend: (n) => ['function', 'method', 'class', 'module', 'api_endpoint'].includes(n.kind),
    Frontend: (n) => ['component', 'page', 'hook', 'route'].includes(n.kind),
    Tests: (n) => n.kind === 'test',
    Reviews: (n) => n.kind === 'pattern' || n.kind === 'security_surface',
    Refactors: (n) => (n.suggested_improvements || []).length > 0,
    'Current State': () => true,
  };
  const fn = map[stage] || (() => false);
  return nodes.filter(fn).slice(0, 40);
}
function countBy(arr, fn) {
  const o = {};
  arr.forEach((x) => { const k = fn(x); o[k] = (o[k] || 0) + 1; });
  return o;
}
function shortId(id) { return id ? id.slice(0, 10) + '…' : '—'; }
function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

let _shell = null;
export function getLivingShell() {
  if (!_shell) _shell = new LivingShell();
  return _shell;
}
