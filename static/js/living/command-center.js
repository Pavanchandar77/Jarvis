/** Universal Command Center palette */

const COMMANDS = [
  { id: 'explain', label: 'Explain selection / symbol', hint: 'Universal Explain from Twin', view: null },
  { id: 'architecture', label: 'Open Live Architecture', hint: 'Architecture Canvas', view: 'architecture' },
  { id: 'review', label: 'Review Architecture', hint: 'One-click twin-backed review', view: 'review' },
  { id: 'simulate', label: 'Simulate Change', hint: 'Impact analysis without edits', view: 'learning' },
  { id: 'timeline', label: 'Project Time Travel', hint: 'Checkpoints & scrub', view: 'timeline' },
  { id: 'runtime', label: 'Runtime Visualization', hint: 'Digital twin of inference/runtime', view: 'runtime' },
  { id: 'replay', label: 'Build Replay', hint: 'How the app was built', view: 'replay' },
  { id: 'learning', label: 'Teach This Component', hint: 'Tutorial / quiz / simulate', view: 'learning' },
  { id: 'mission', label: 'Mission Control', hint: 'Workspace overview', view: 'mission' },
  { id: 'knowledge', label: 'Search Knowledge Memory', hint: 'Org memory', view: 'knowledge' },
  { id: 'coding', label: 'Open Coding Mode', hint: 'Editor workspace', view: null },
  { id: 'twin', label: 'Open Semantic Twin Explorer', hint: 'Living graph explorer', view: null },
  { id: 'deadcode', label: 'Find Dead Code', hint: 'Low dependents / unused', view: 'architecture' },
  { id: 'diagram', label: 'Generate Diagram View', hint: 'Architecture canvas', view: 'architecture' },
  { id: 'execution', label: 'Open Execution Replay', hint: 'Animate path', view: 'runtime' },
  { id: 'optimize', label: 'Optimize Runtime', hint: 'Runtime metrics focus', view: 'runtime' },
];

export class CommandCenter {
  constructor({ onAction } = {}) {
    this.onAction = onAction || (() => {});
    this.el = null;
    this.filter = '';
    this.active = 0;
  }

  ensure() {
    if (this.el) return;
    this.el = document.createElement('div');
    this.el.id = 'lv-cmd-palette';
    this.el.innerHTML = `
      <div class="lv-cmd-box" role="dialog" aria-label="Command Center">
        <input type="search" placeholder="Command Center — type an action…" data-role="q" autocomplete="off" />
        <div class="lv-cmd-list" data-role="list"></div>
      </div>
    `;
    document.body.appendChild(this.el);
    const input = this.el.querySelector('[data-role="q"]');
    input.addEventListener('input', () => {
      this.filter = input.value;
      this.active = 0;
      this._render();
    });
    input.addEventListener('keydown', (e) => {
      const items = this._filtered();
      if (e.key === 'ArrowDown') { e.preventDefault(); this.active = Math.min(items.length - 1, this.active + 1); this._render(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); this.active = Math.max(0, this.active - 1); this._render(); }
      else if (e.key === 'Enter') { e.preventDefault(); if (items[this.active]) this._run(items[this.active]); }
      else if (e.key === 'Escape') { this.close(); }
    });
    this.el.addEventListener('click', (e) => {
      if (e.target === this.el) this.close();
    });
  }

  open() {
    this.ensure();
    this.el.classList.add('open');
    this.filter = '';
    this.active = 0;
    const input = this.el.querySelector('[data-role="q"]');
    input.value = '';
    this._render();
    setTimeout(() => input.focus(), 20);
  }

  close() {
    if (this.el) this.el.classList.remove('open');
  }

  toggle() {
    if (this.el?.classList.contains('open')) this.close();
    else this.open();
  }

  _filtered() {
    const q = this.filter.toLowerCase().trim();
    if (!q) return COMMANDS;
    return COMMANDS.filter((c) =>
      c.label.toLowerCase().includes(q) || c.hint.toLowerCase().includes(q) || c.id.includes(q)
    );
  }

  _render() {
    const list = this.el.querySelector('[data-role="list"]');
    const items = this._filtered();
    list.innerHTML = items.map((c, i) =>
      `<div class="lv-cmd-item ${i === this.active ? 'active' : ''}" data-id="${c.id}">
        ${c.label}<div class="hint">${c.hint}</div>
      </div>`
    ).join('') || `<div class="lv-cmd-item">No commands</div>`;
    list.querySelectorAll('.lv-cmd-item[data-id]').forEach((el) => {
      el.addEventListener('click', () => {
        const cmd = COMMANDS.find((c) => c.id === el.dataset.id);
        if (cmd) this._run(cmd);
      });
    });
  }

  _run(cmd) {
    this.close();
    this.onAction(cmd);
  }
}

export { COMMANDS };
