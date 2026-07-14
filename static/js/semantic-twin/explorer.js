/**
 * Semantic Twin Explorer — living system shell
 */

import TwinApiClient from './api-client.js';
import { GraphRenderer } from './graph-renderer.js';
import { NodePanel } from './node-panel.js';
import { AnimationController } from './animation-pipeline.js';
import { STORY_STAGES } from './view-modes.js';

export class SemanticTwinExplorer {
  /**
   * @param {HTMLElement} mount
   * @param {{ twinId?: string }} opts
   */
  constructor(mount, opts = {}) {
    this.mount = mount;
    this.twinId = opts.twinId || null;
    this.twin = null;
    this.nodesById = new Map();
    this.mode = 'beginner';
    this._build();
  }

  _build() {
    this.mount.classList.add('st-explorer');
    this.mount.innerHTML = `
      <div class="st-toolbar">
        <div class="st-brand">Semantic Twin</div>
        <input class="st-search" type="search" placeholder="Search nodes, concepts…" data-role="search" />
        <select class="st-twin-select" data-role="twins"></select>
        <button type="button" class="st-btn" data-role="play">Play story</button>
        <button type="button" class="st-btn" data-role="pause">Pause</button>
        <div class="st-story-track" data-role="story"></div>
      </div>
      <div class="st-main">
        <canvas class="st-canvas" data-role="canvas"></canvas>
        <aside class="st-side" data-role="panel"></aside>
      </div>
      <div class="st-search-results" data-role="results" hidden></div>
    `;

    const canvas = this.mount.querySelector('[data-role="canvas"]');
    this.renderer = new GraphRenderer(canvas, {
      onSelect: (node) => this.selectNode(node.id),
    });
    this.panel = new NodePanel(this.mount.querySelector('[data-role="panel"]'));
    this.panel.onModeChange((mode) => {
      this.mode = mode;
      if (this.selectedId) this._refreshExplain(this.selectedId);
    });
    this.panel.onRelated((id) => this.selectNode(id));

    this.anim = new AnimationController({
      onStep: (step) => this._onAnimStep(step),
      onComplete: () => this.renderer.stopPulse(),
    });

    this.mount.querySelector('[data-role="play"]').addEventListener('click', () => this.anim.play());
    this.mount.querySelector('[data-role="pause"]').addEventListener('click', () => this.anim.pause());

    const search = this.mount.querySelector('[data-role="search"]');
    let t = null;
    search.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => this._search(search.value), 200);
    });

    this.mount.querySelector('[data-role="twins"]').addEventListener('change', (e) => {
      if (e.target.value) this.loadTwin(e.target.value);
    });

    const story = this.mount.querySelector('[data-role="story"]');
    STORY_STAGES.forEach((s) => {
      const el = document.createElement('span');
      el.className = 'st-story-stage';
      el.dataset.kind = s.id;
      el.style.setProperty('--c', s.color);
      el.textContent = s.label;
      el.title = s.label;
      el.addEventListener('click', () => this.anim.skipTo(s.id));
      story.appendChild(el);
    });

    const ro = new ResizeObserver(() => this._resize());
    ro.observe(this.mount.querySelector('.st-main'));
  }

  async init() {
    await this._loadTwinList();
    if (this.twinId) await this.loadTwin(this.twinId);
  }

  async _loadTwinList() {
    const sel = this.mount.querySelector('[data-role="twins"]');
    try {
      // Prefer registered projects (Phase 1 automatic registration)
      let options = [];
      try {
        const proj = await TwinApiClient.listProjects();
        options = (proj.projects || [])
          .filter((p) => p.twin_id)
          .map((p) =>
            `<option value="${escapeHtml(p.twin_id)}">${escapeHtml(p.name)} · r${p.last_revision || 0}</option>`
          );
      } catch (_) { /* fall through */ }
      if (!options.length) {
        const data = await TwinApiClient.list();
        options = (data.twins || []).map((t) =>
          `<option value="${escapeHtml(t.twin_id)}">${escapeHtml(t.meta?.application_name || t.application_id)} (r${t.content_revision})</option>`
        );
      }
      sel.innerHTML = `<option value="">Projects / Twins…</option>` + options.join('');
      if (this.twinId) sel.value = this.twinId;
    } catch (err) {
      sel.innerHTML = `<option value="">${escapeHtml(err.message)}</option>`;
    }
  }

  async loadTwin(twinId) {
    this.twinId = twinId;
    const graph = await TwinApiClient.graph(twinId);
    this.twin = graph;
    this.nodesById = new Map((graph.nodes || []).map((n) => [n.id, n]));
    this.renderer.setGraph(graph.nodes || [], graph.edges || []);
    this._resize();
    const sel = this.mount.querySelector('[data-role="twins"]');
    if (sel) sel.value = twinId;
  }

  async selectNode(nodeId) {
    const node = this.nodesById.get(nodeId);
    if (!node || !this.twinId) return;
    this.selectedId = nodeId;
    this.renderer.setSelection(nodeId);
    this.renderer.startPulse();
    await this._refreshExplain(nodeId);
    try {
      const story = await TwinApiClient.story(this.twinId, nodeId);
      this.anim.load(story.steps || []);
      this.anim.play();
    } catch (_) {
      this.anim.load([]);
    }
  }

  async _refreshExplain(nodeId) {
    const node = this.nodesById.get(nodeId);
    if (!node) return;
    try {
      const explain = await TwinApiClient.explain(this.twinId, {
        node_id: nodeId,
        mode: this.mode,
      });
      this.panel.showNode(node, explain);
    } catch (_) {
      this.panel.showNode(node, null);
    }
  }

  _onAnimStep(step) {
    this.mount.querySelectorAll('.st-story-stage').forEach((el) => {
      el.classList.toggle('active', el.dataset.kind === step.kind);
    });
    this.renderer.setHighlight(step.node_ids || [], step.edge_ids || []);
    if (step.panel_mode && step.panel_mode !== this.mode) {
      this.mode = step.panel_mode;
      this.panel.setMode(step.panel_mode);
    }
    const focus = (step.node_ids || [])[0];
    if (focus && this.nodesById.has(focus)) {
      this.renderer.setSelection(focus);
      this._refreshExplain(focus);
    }
  }

  async _search(q) {
    const box = this.mount.querySelector('[data-role="results"]');
    if (!q || !this.twinId) {
      box.hidden = true;
      return;
    }
    const res = await TwinApiClient.search(this.twinId, { q, limit: 12 });
    const hits = res.hits || [];
    box.hidden = false;
    box.innerHTML = hits.map((h) =>
      `<button type="button" class="st-result" data-id="${escapeHtml(h.node_id)}">
        <strong>${escapeHtml(h.name)}</strong>
        <span>${escapeHtml(h.kind)}</span>
        <em>${escapeHtml(h.snippet || '')}</em>
      </button>`
    ).join('') || `<div class="st-muted">No results</div>`;
    box.querySelectorAll('.st-result').forEach((btn) => {
      btn.addEventListener('click', () => {
        box.hidden = true;
        this.selectNode(btn.dataset.id);
      });
    });
  }

  _resize() {
    const main = this.mount.querySelector('.st-main');
    const canvas = this.mount.querySelector('[data-role="canvas"]');
    if (!main || !canvas) return;
    const rect = main.getBoundingClientRect();
    const side = this.mount.querySelector('.st-side');
    const sideW = side ? side.getBoundingClientRect().width : 0;
    this.renderer.resize(Math.max(320, rect.width - sideW), Math.max(280, rect.height));
  }
}

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export default SemanticTwinExplorer;
