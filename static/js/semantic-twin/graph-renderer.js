/**
 * Force-ish graph renderer with LOD for large twins.
 * Canvas-based living system visualization.
 */

import { KIND_COLORS } from './view-modes.js';

const MAX_RENDER = 400;

export class GraphRenderer {
  constructor(canvas, { onSelect } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.onSelect = onSelect || (() => {});
    this.nodes = [];
    this.edges = [];
    this.pos = new Map();
    this.selected = null;
    this.highlight = new Set();
    this.highlightEdges = new Set();
    this.scale = 1;
    this.ox = 0;
    this.oy = 0;
    this._drag = null;
    this._pulse = 0;
    this._raf = null;
    this._bind();
  }

  setGraph(nodes, edges) {
    // LOD: prefer code-ish nodes if too many
    let list = nodes.slice();
    if (list.length > MAX_RENDER) {
      const priority = new Set([
        'component', 'function', 'api_endpoint', 'route', 'class',
        'concept', 'prompt', 'design_decision', 'application',
      ]);
      list = list.filter((n) => priority.has(n.kind)).slice(0, MAX_RENDER);
    }
    this.nodes = list;
    const ids = new Set(list.map((n) => n.id));
    this.edges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    this._layout();
    this.draw();
  }

  setSelection(nodeId) {
    this.selected = nodeId;
    this.draw();
  }

  setHighlight(nodeIds = [], edgeIds = []) {
    this.highlight = new Set(nodeIds);
    this.highlightEdges = new Set(edgeIds);
    this.draw();
  }

  startPulse() {
    if (this._raf) return;
    const tick = () => {
      this._pulse = (this._pulse + 0.05) % (Math.PI * 2);
      this.draw();
      this._raf = requestAnimationFrame(tick);
    };
    this._raf = requestAnimationFrame(tick);
  }

  stopPulse() {
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = null;
  }

  _layout() {
    const w = this.canvas.width || 800;
    const h = this.canvas.height || 600;
    const n = this.nodes.length || 1;
    this.pos.clear();
    // Simple golden-angle spiral + jitter by kind rings
    const kindRing = {
      application: 0.15, prompt: 0.35, concept: 0.9,
      module: 0.45, component: 0.55, function: 0.65,
      api_endpoint: 0.7, route: 0.7, design_decision: 0.4,
    };
    this.nodes.forEach((node, i) => {
      const ring = kindRing[node.kind] ?? 0.6;
      const angle = i * 2.399963 + (node.kind || '').length;
      const r = Math.min(w, h) * 0.12 + ring * Math.min(w, h) * 0.35;
      this.pos.set(node.id, {
        x: w / 2 + Math.cos(angle) * r,
        y: h / 2 + Math.sin(angle) * r,
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

    // Edges
    for (const e of this.edges) {
      const a = this.pos.get(e.source);
      const b = this.pos.get(e.target);
      if (!a || !b) continue;
      const hi = this.highlightEdges.has(e.id) ||
        (this.highlight.has(e.source) && this.highlight.has(e.target));
      ctx.strokeStyle = hi ? `rgba(168, 85, 247, ${0.55 + 0.35 * Math.sin(this._pulse)})` : 'rgba(148,163,184,0.25)';
      ctx.lineWidth = hi ? 2.2 : 1;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }

    // Nodes
    for (const n of this.nodes) {
      const p = this.pos.get(n.id);
      if (!p) continue;
      const color = KIND_COLORS[n.kind] || '#94a3b8';
      const selected = this.selected === n.id;
      const hi = this.highlight.has(n.id);
      const radius = selected ? 10 : hi ? 8 : 6;
      ctx.beginPath();
      ctx.fillStyle = color;
      ctx.globalAlpha = hi || selected || !this.highlight.size ? 1 : 0.35;
      ctx.arc(p.x, p.y, radius + (hi ? 2 * Math.sin(this._pulse) : 0), 0, Math.PI * 2);
      ctx.fill();
      if (selected) {
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      if (selected || hi || this.nodes.length < 80) {
        ctx.fillStyle = '#e2e8f0';
        ctx.font = '11px system-ui, sans-serif';
        ctx.fillText(n.name.slice(0, 28), p.x + 10, p.y + 4);
      }
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
        if (d < bestD) {
          bestD = d;
          best = n;
        }
      }
      if (best) {
        this.setSelection(best.id);
        this.onSelect(best);
      }
    });

    this.canvas.addEventListener('wheel', (ev) => {
      ev.preventDefault();
      const delta = ev.deltaY > 0 ? 0.9 : 1.1;
      this.scale = Math.min(3, Math.max(0.3, this.scale * delta));
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

  resize(width, height) {
    this.canvas.width = width;
    this.canvas.height = height;
    this._layout();
    this.draw();
  }
}

export default GraphRenderer;
