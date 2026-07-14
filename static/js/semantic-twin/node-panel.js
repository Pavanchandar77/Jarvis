/** Multi-mode node explanation panel */

import { VIEWING_MODES } from './view-modes.js';

export class NodePanel {
  constructor(rootEl) {
    this.root = rootEl;
    this.mode = 'beginner';
    this.node = null;
    this.explain = null;
    this._renderShell();
  }

  _renderShell() {
    this.root.innerHTML = `
      <div class="st-panel-header">
        <div class="st-panel-title" data-role="title">Select a node</div>
        <div class="st-panel-meta" data-role="meta"></div>
      </div>
      <div class="st-mode-tabs" data-role="tabs"></div>
      <div class="st-panel-body" data-role="body">
        <p class="st-muted">Click a component in the living graph to explore its story.</p>
      </div>
      <div class="st-panel-related" data-role="related"></div>
    `;
    const tabs = this.root.querySelector('[data-role="tabs"]');
    VIEWING_MODES.forEach((m) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'st-mode-tab' + (m.id === this.mode ? ' active' : '');
      btn.dataset.mode = m.id;
      btn.title = m.hint;
      btn.textContent = m.label;
      btn.addEventListener('click', () => this.setMode(m.id));
      tabs.appendChild(btn);
    });
  }

  setMode(mode) {
    this.mode = mode;
    this.root.querySelectorAll('.st-mode-tab').forEach((el) => {
      el.classList.toggle('active', el.dataset.mode === mode);
    });
    if (this._onMode) this._onMode(mode);
    this._paint();
  }

  onModeChange(fn) {
    this._onMode = fn;
  }

  showNode(node, explainResult) {
    this.node = node;
    this.explain = explainResult;
    this._paint();
  }

  _paint() {
    const title = this.root.querySelector('[data-role="title"]');
    const meta = this.root.querySelector('[data-role="meta"]');
    const body = this.root.querySelector('[data-role="body"]');
    const related = this.root.querySelector('[data-role="related"]');
    if (!this.node) return;

    title.textContent = this.node.name;
    meta.textContent = `${this.node.kind} · difficulty ${(this.node.difficulty_score ?? 0).toFixed(2)}`;

    const content = this.explain?.content
      || this.node.views?.[this.mode]
      || { title: this.node.name, body: this.node.purpose || this.node.description || '' };

    const bullets = (content.bullets || []).map((b) => `<li>${escapeHtml(b)}</li>`).join('');
    const warnings = (content.warnings || []).map((w) => `<div class="st-warn">${escapeHtml(w)}</div>`).join('');
    body.innerHTML = `
      <h3>${escapeHtml(content.title || this.node.name)}</h3>
      <p>${formatBody(content.body || '')}</p>
      ${bullets ? `<ul>${bullets}</ul>` : ''}
      ${warnings}
      ${this.node.source_file ? `<div class="st-source">${escapeHtml(this.node.source_file)}${this.node.source_location ? ':' + this.node.source_location.start_line : ''}</div>` : ''}
    `;

    const rel = this.explain?.related || [];
    related.innerHTML = rel.length
      ? `<div class="st-related-label">Related</div>` +
        rel.map((r) => `<button type="button" class="st-chip" data-id="${escapeHtml(r.id)}">${escapeHtml(r.name)}</button>`).join('')
      : '';
    related.querySelectorAll('.st-chip').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (this._onRelated) this._onRelated(btn.dataset.id);
      });
    });
  }

  onRelated(fn) {
    this._onRelated = fn;
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatBody(s) {
  return escapeHtml(s).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>');
}

export default NodePanel;
