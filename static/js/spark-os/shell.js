/**
 * Spark OS Shell — multi-panel surface for Phase 2 capabilities.
 * Integrates with Semantic Twin explorer via twin_id query param.
 */
import SparkOSClient from './api-client.js';

const PANELS = [
  { id: 'overview', label: 'Overview' },
  { id: 'architecture', label: 'Architecture' },
  { id: 'requirements', label: 'Requirements' },
  { id: 'review', label: 'Review' },
  { id: 'agents', label: 'Agents' },
  { id: 'timeline', label: 'Time Machine' },
  { id: 'simulate', label: 'Simulate' },
  { id: 'runtime', label: 'Runtime' },
  { id: 'marketplace', label: 'Marketplace' },
  { id: 'refactor', label: 'Refactor' },
  { id: 'memory', label: 'Org Memory' },
];

export class SparkOSShell {
  constructor(mount, { twinId } = {}) {
    this.mount = mount;
    this.twinId = twinId || null;
    this.panel = 'overview';
    this._build();
  }

  _build() {
    this.mount.classList.add('sos-shell');
    this.mount.innerHTML = `
      <header class="sos-header">
        <div class="sos-brand">Spark OS</div>
        <input class="sos-twin" data-role="twin" placeholder="twin_id" value="${escape(this.twinId || '')}" />
        <nav class="sos-nav" data-role="nav"></nav>
      </header>
      <main class="sos-main" data-role="main">
        <p class="sos-muted">Select a capability. Semantic Twin is the canonical model.</p>
      </main>
    `;
    const nav = this.mount.querySelector('[data-role="nav"]');
    PANELS.forEach((p) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = p.label;
      b.dataset.panel = p.id;
      b.className = 'sos-tab' + (p.id === this.panel ? ' active' : '');
      b.addEventListener('click', () => this.show(p.id));
      nav.appendChild(b);
    });
    this.mount.querySelector('[data-role="twin"]').addEventListener('change', (e) => {
      this.twinId = e.target.value.trim() || null;
    });
    this.show('overview');
  }

  async show(panel) {
    this.panel = panel;
    this.mount.querySelectorAll('.sos-tab').forEach((el) => {
      el.classList.toggle('active', el.dataset.panel === panel);
    });
    const main = this.mount.querySelector('[data-role="main"]');
    main.innerHTML = `<p class="sos-muted">Loading ${panel}…</p>`;
    try {
      if (panel === 'overview') main.innerHTML = await this._overview();
      else if (panel === 'architecture') main.innerHTML = await this._architecture();
      else if (panel === 'requirements') main.innerHTML = await this._requirements();
      else if (panel === 'review') main.innerHTML = await this._review();
      else if (panel === 'agents') main.innerHTML = await this._agents();
      else if (panel === 'timeline') main.innerHTML = await this._timeline();
      else if (panel === 'simulate') main.innerHTML = await this._simulate();
      else if (panel === 'runtime') main.innerHTML = await this._runtime();
      else if (panel === 'marketplace') main.innerHTML = await this._marketplace();
      else if (panel === 'refactor') main.innerHTML = await this._refactor();
      else if (panel === 'memory') main.innerHTML = await this._memory();
    } catch (err) {
      main.innerHTML = `<p class="sos-error">${escape(err.message)}</p>`;
    }
    this._wire(main);
  }

  async _overview() {
    const st = await SparkOSClient.status();
    return `
      <h2>Software Operating System</h2>
      <p>Canonical model: <code>${escape(st.canonical_model)}</code></p>
      <ul class="sos-caps">${(st.capabilities || []).map((c) => `<li>${escape(c)}</li>`).join('')}</ul>
      <p class="sos-muted">Twin explorer: <a href="/semantic-twin${this.twinId ? `?twin=${encodeURIComponent(this.twinId)}` : ''}">Open Semantic Twin</a></p>
    `;
  }

  async _architecture() {
    const list = await SparkOSClient.listArchitectures();
    const rows = (list.architectures || []).slice(0, 20);
    return `
      <h2>Architecture-First</h2>
      <p>Design systems before code. Compile to implementation + twin.</p>
      <div class="sos-actions">
        <button type="button" data-act="design-saas">New SaaS-style design</button>
      </div>
      <ul>${rows.map((a) => `<li><strong>${escape(a.name)}</strong> <code>${escape(a.architecture_id.slice(0, 8))}</code> v${a.version}</li>`).join('') || '<li class="sos-muted">No architectures yet</li>'}</ul>
    `;
  }

  async _requirements() {
    if (!this.twinId) return needTwin();
    const data = await SparkOSClient.listRequirements(this.twinId);
    const reqs = data.requirements || [];
    return `
      <h2>Living Requirements</h2>
      <ul>${reqs.map((r) => `
        <li>
          <strong>${escape(r.text.slice(0, 120))}</strong>
          <button type="button" data-act="trace-req" data-id="${escape(r.id)}">Trace</button>
        </li>`).join('') || '<li class="sos-muted">No requirements on twin</li>'}
      </ul>
      <pre data-role="trace" class="sos-pre"></pre>
    `;
  }

  async _review() {
    if (!this.twinId) return needTwin();
    const report = await SparkOSClient.review(this.twinId);
    return `
      <h2>Architecture Review</h2>
      <p>Overall score: <strong>${report.overall}</strong></p>
      <div class="sos-scores">${Object.entries(report.scores || {}).map(([k, v]) =>
        `<span class="sos-chip">${escape(k)}: ${v}</span>`).join('')}</div>
      <ul>${(report.findings || []).slice(0, 15).map((f) =>
        `<li class="sev-${escape(f.severity)}"><strong>${escape(f.severity)}</strong> ${escape(f.title)} — ${escape(f.explanation)}</li>`
      ).join('')}</ul>
    `;
  }

  async _agents() {
    if (!this.twinId) return needTwin();
    await SparkOSClient.agentBootstrap(this.twinId);
    // project_id often equals application_id; status by twin for now uses twin as key after bootstrap
    const st = await SparkOSClient.agentStatus(this.twinId);
    return `
      <h2>Multi-Agent Workspace</h2>
      <p>Roles: ${(st.roles || []).join(', ')}</p>
      <p>Ownership bindings: ${st.ownership_count || 0} · Open messages: ${st.open_messages || 0}</p>
      <p>Conflicts: ${JSON.stringify(st.conflicts || [])}</p>
    `;
  }

  async _timeline() {
    if (!this.twinId) return needTwin();
    const h = await SparkOSClient.timeline(this.twinId);
    const versions = h.versions || [];
    return `
      <h2>Project Time Machine</h2>
      <div class="sos-scrub">
        ${(versions).map((v) =>
          `<button type="button" data-act="scrub" data-rev="${v.revision}">r${v.revision} · ${escape(v.trigger || '')}</button>`
        ).join('') || '<span class="sos-muted">No versions</span>'}
      </div>
      <pre data-role="scrub-out" class="sos-pre"></pre>
    `;
  }

  async _simulate() {
    if (!this.twinId) return needTwin();
    return `
      <h2>Simulation Engine</h2>
      <p>No source code is modified.</p>
      <textarea data-role="proposal" rows="3" class="sos-input">Split the auth service into a separate microservice</textarea>
      <button type="button" data-act="run-sim">Simulate</button>
      <pre data-role="sim-out" class="sos-pre"></pre>
    `;
  }

  async _runtime() {
    if (!this.twinId) return needTwin();
    const viz = await SparkOSClient.runtimeViz(this.twinId);
    const frames = viz.frames || [];
    return `
      <h2>Live Runtime Visualization</h2>
      <p>${escape(viz.path_label || '')}</p>
      <ol class="sos-frames">${frames.map((f) =>
        `<li class="hl-${escape(f.highlight)}"><strong>${escape(f.stage)}</strong> — ${escape(f.label)} (${(f.node_ids || []).length} nodes)</li>`
      ).join('')}</ol>
      <p>Bottlenecks: ${(viz.bottlenecks || []).length} · Failures: ${(viz.failures || []).length}</p>
    `;
  }

  async _marketplace() {
    const data = await SparkOSClient.marketplace();
    const items = data.architectures || [];
    return `
      <h2>Architecture Marketplace</h2>
      <div class="sos-grid">${items.map((a) => `
        <article class="sos-card">
          <h3>${escape(a.name)}</h3>
          <p>${escape(a.description)}</p>
          <p class="sos-muted">${escape(a.rationale || '')}</p>
          <button type="button" data-act="use-arch" data-slug="${escape(a.slug)}">Use architecture</button>
        </article>`).join('')}</div>
    `;
  }

  async _refactor() {
    if (!this.twinId) return needTwin();
    const cat = await SparkOSClient.refactorCatalog();
    return `
      <h2>Autonomous Refactoring</h2>
      <ul>${(cat.transformations || []).map((t) => `
        <li>
          <strong>${escape(t.title)}</strong>
          <button type="button" data-act="refactor" data-id="${escape(t.id)}">Run pipeline</button>
        </li>`).join('')}</ul>
      <pre data-role="ref-out" class="sos-pre"></pre>
    `;
  }

  async _memory() {
    const hits = await SparkOSClient.memorySearch('api security testing');
    return `
      <h2>Organizational Knowledge Memory</h2>
      <ul>${(hits.hits || []).map((h) =>
        `<li><strong>${escape(h.kind)}</strong> ${escape(h.title)} — ${escape((h.summary || '').slice(0, 140))}</li>`
      ).join('') || '<li class="sos-muted">Memory empty — compile/review projects to learn</li>'}</ul>
    `;
  }

  _wire(main) {
    main.querySelector('[data-act="design-saas"]')?.addEventListener('click', async () => {
      await SparkOSClient.design({
        name: 'New SaaS Design',
        services: ['api', 'auth', 'billing'],
        databases: ['app_db'],
        apis: [{ name: 'Health', method: 'GET', path: '/health' }],
      });
      this.show('architecture');
    });
    main.querySelectorAll('[data-act="trace-req"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const out = await SparkOSClient.traceRequirement(this.twinId, btn.dataset.id);
        main.querySelector('[data-role="trace"]').textContent = JSON.stringify(out, null, 2);
      });
    });
    main.querySelectorAll('[data-act="scrub"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const out = await SparkOSClient.scrub(this.twinId, Number(btn.dataset.rev));
        main.querySelector('[data-role="scrub-out"]').textContent = JSON.stringify(out, null, 2);
      });
    });
    main.querySelector('[data-act="run-sim"]')?.addEventListener('click', async () => {
      const proposal = main.querySelector('[data-role="proposal"]').value;
      const out = await SparkOSClient.simulate(this.twinId, { proposal });
      main.querySelector('[data-role="sim-out"]').textContent = JSON.stringify(out, null, 2);
    });
    main.querySelectorAll('[data-act="use-arch"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const out = await SparkOSClient.marketplaceUse(btn.dataset.slug);
        alert(`Architecture created: ${out.architecture?.architecture_id || 'ok'}`);
      });
    });
    main.querySelectorAll('[data-act="refactor"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const out = await SparkOSClient.refactor(this.twinId, {
          transformation: btn.dataset.id,
          full_pipeline: true,
        });
        main.querySelector('[data-role="ref-out"]').textContent = JSON.stringify(out, null, 2);
      });
    });
  }
}

function needTwin() {
  return `<p class="sos-error">Set a twin_id in the header first (generate or open a project).</p>`;
}

function escape(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export default SparkOSShell;
