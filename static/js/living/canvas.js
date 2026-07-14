/** Live Architecture Canvas — nodes are Twin entities */

const LAYER_COLORS = {
  frontend: '#22c55e',
  component: '#22c55e',
  page: '#4ade80',
  route: '#86efac',
  api: '#f97316',
  api_endpoint: '#f97316',
  service: '#3b82f6',
  module: '#60a5fa',
  function: '#93c5fd',
  class: '#6366f1',
  database: '#eab308',
  table: '#eab308',
  column: '#facc15',
  queue: '#a855f7',
  event: '#c084fc',
  event_handler: '#d8b4fe',
  job: '#a855f7',
  storage: '#14b8a6',
  external: '#f472b6',
  security_surface: '#ef4444',
  requirement: '#38bdf8',
  design_decision: '#eab308',
  application: '#94a3b8',
};

const LAYER_OF = {
  component: 'frontend', page: 'frontend', route: 'frontend', hook: 'frontend', state_atom: 'frontend',
  api_endpoint: 'api', middleware: 'api',
  function: 'service', method: 'service', class: 'service', module: 'service', package: 'service',
  table: 'database', column: 'database', migration: 'database',
  event: 'queue', event_handler: 'queue', subscription: 'queue', job: 'queue',
  storage: 'storage', blob: 'storage', file_store: 'storage',
  external: 'external', external_api: 'external', third_party: 'external',
  security_surface: 'security',
};

export class ArchitectureCanvas {
  constructor(canvas, { onSelect } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.onSelect = onSelect || (() => {});
    this.nodes = [];
    this.edges = [];
    this.pos = new Map();
    this.selected = null;
    this.highlight = new Set();
    this.scale = 1;
    this.ox = 0;
    this.oy = 0;
    this._drag = null;
    this._bind();
  }

  setGraph(nodes, edges) {
    // Prefer architectural kinds; LOD if huge
    const priority = new Set([
      'application', 'module', 'package', 'component', 'page', 'route',
      'api_endpoint', 'function', 'class', 'table', 'event', 'event_handler',
      'security_surface', 'requirement', 'design_decision',
    ]);
    let list = (nodes || []).filter((n) => priority.has(n.kind) || (n.attributes || {}).architecture_kind);
    if (list.length > 350) list = list.slice(0, 350);
    this.nodes = list;
    const ids = new Set(list.map((n) => n.id));
    this.edges = (edges || []).filter((e) => ids.has(e.source) && ids.has(e.target));
    this._layout();
    this.draw();
  }

  setSelection(id) {
    this.selected = id;
    this.draw();
  }

  setHighlight(ids = []) {
    this.highlight = new Set(ids);
    this.draw();
  }

  resize() {
    const p = this.canvas.parentElement;
    if (!p) return;
    const r = p.getBoundingClientRect();
    this.canvas.width = Math.max(320, r.width);
    this.canvas.height = Math.max(280, r.height);
    this._layout();
    this.draw();
  }

  _layout() {
    const w = this.canvas.width || 800;
    const h = this.canvas.height || 500;
    const lanes = {
      frontend: 0.10, api: 0.22, service: 0.36, database: 0.50,
      queue: 0.62, storage: 0.72, external: 0.82, security: 0.90, other: 0.96,
    };
    const buckets = {};
    this.nodes.forEach((n) => {
      const layer = LAYER_OF[n.kind] || (n.attributes || {}).architecture_kind || 'other';
      const key = lanes[layer] != null ? layer : 'other';
      (buckets[key] ||= []).push(n);
    });
    this.pos.clear();
    Object.entries(buckets).forEach(([layer, list]) => {
      const y = h * (lanes[layer] || 0.5);
      list.forEach((n, i) => {
        const x = w * (0.08 + 0.84 * ((i + 0.5) / Math.max(list.length, 1)));
        this.pos.set(n.id, { x, y: y + (i % 3 - 1) * 14 });
      });
    });
  }

  draw() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(this.ox, this.oy);
    ctx.scale(this.scale, this.scale);

    for (const e of this.edges) {
      const a = this.pos.get(e.source);
      const b = this.pos.get(e.target);
      if (!a || !b) continue;
      const hi = this.highlight.has(e.source) && this.highlight.has(e.target);
      ctx.strokeStyle = hi ? 'rgba(168,85,247,0.85)' : 'rgba(148,163,184,0.22)';
      ctx.lineWidth = hi ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }

    for (const n of this.nodes) {
      const p = this.pos.get(n.id);
      if (!p) continue;
      const color = LAYER_COLORS[n.kind] || LAYER_COLORS[LAYER_OF[n.kind]] || '#94a3b8';
      const sel = this.selected === n.id;
      const hi = this.highlight.has(n.id);
      const r = sel ? 9 : hi ? 7 : 5;
      ctx.globalAlpha = !this.highlight.size || hi || sel ? 1 : 0.28;
      ctx.beginPath();
      ctx.fillStyle = color;
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fill();
      if (sel) {
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      if (sel || hi || this.nodes.length < 60) {
        ctx.fillStyle = '#e2e8f0';
        ctx.font = '11px system-ui,sans-serif';
        ctx.fillText((n.name || '').slice(0, 24), p.x + 10, p.y + 3);
      }
      ctx.globalAlpha = 1;
    }
    ctx.restore();
  }

  _bind() {
    this.canvas.addEventListener('click', (ev) => {
      const rect = this.canvas.getBoundingClientRect();
      const x = (ev.clientX - rect.left - this.ox) / this.scale;
      const y = (ev.clientY - rect.top - this.oy) / this.scale;
      let best = null;
      let bestD = 14;
      for (const n of this.nodes) {
        const p = this.pos.get(n.id);
        if (!p) continue;
        const d = Math.hypot(p.x - x, p.y - y);
        if (d < bestD) { bestD = d; best = n; }
      }
      if (best) {
        this.setSelection(best.id);
        this.onSelect(best);
      }
    });
    this.canvas.addEventListener('wheel', (ev) => {
      ev.preventDefault();
      this.scale = Math.min(3, Math.max(0.35, this.scale * (ev.deltaY > 0 ? 0.9 : 1.1)));
      this.draw();
    }, { passive: false });
    this.canvas.addEventListener('pointerdown', (ev) => {
      this._drag = { x: ev.clientX, y: ev.clientY, ox: this.ox, oy: this.oy };
    });
    window.addEventListener('pointerup', () => { this._drag = null; });
    window.addEventListener('pointermove', (ev) => {
      if (!this._drag) return;
      this.ox = this._drag.ox + (ev.clientX - this._drag.x);
      this.oy = this._drag.oy + (ev.clientY - this._drag.y);
      this.draw();
    });
  }
}

export function layerLegendHtml() {
  const items = [
    ['Frontend', '#22c55e'], ['API', '#f97316'], ['Service', '#3b82f6'],
    ['Database', '#eab308'], ['Queue/Jobs', '#a855f7'], ['Storage', '#14b8a6'],
    ['External', '#f472b6'], ['Security', '#ef4444'],
  ];
  return items.map(([l, c]) =>
    `<span style="border-color:${c}55;color:${c}">${l}</span>`
  ).join('');
}
