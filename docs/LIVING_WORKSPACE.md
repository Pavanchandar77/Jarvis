# Living Software Workspace (UX Phase 2)

Coding Mode remains the editor. This surface makes software **observable, explainable, and replayable** through the Semantic Twin.

The code editor is one view. The **Semantic Twin is the source of truth.** Everything else derives from it.

## Principles

* Every interaction answers: What is this? Why? What depends on it? What if I change it? How does it execute? How was it created?
* Never invent architecture solely from source — use Twin relationships.
* Harness-agnostic: OpenCode / Claude Code / Codex plug in without UI redesign.
* Preserve existing Spark UI; do not redesign Chat or Coding Mode layout.

## Navigation

| UI | Route | View |
|----|-------|------|
| Mission Control | `/mission` | Workspace overview dashboard |
| Architecture | `/architecture` | Live Architecture Canvas |
| Runtime | `/runtime-viz` | Runtime Digital Twin |
| Time Travel | `/time-travel` | Project timeline scrub |
| **⌘/Ctrl+K** | global | Command Center |

Rail + Tools: Mission Control, Architecture, Runtime. Coding Mode: `/coding`.

## Deliverables

### 1. Live Architecture Canvas
- Twin nodes/edges, layered (Frontend · API · Service · Database · Queue/Jobs · Storage · External · Security)
- Click node → detail: source, purpose, execution, deps/dependents, metrics, history, prompt, reviews
- Graph refreshes with twin / continuous sync

### 2. Time Travel
- OS timeline checkpoints (code revision · twin · architecture · reviews · simulations)
- Scrub any checkpoint: why / who / what changed / impact / narrative

### 3. Runtime Visualization
- Active model, strategy, VRAM/RAM, SSD streaming, cache, stage, prediction, throughput, latency
- Execution path animation from Runtime Digital Twin frames
- Telemetry via `/api/runtime` + workspace + OS runtime overlay

### 4. Universal Explain
- Coding Mode: select/open symbol → Twin-backed panel (purpose, role, deps, APIs, tables, complexity, improvements)
- Living detail panel on architecture select

### 5. X-Ray Mode
- Coding Mode toggle: hover/cursor illuminates upstream, downstream, layer, APIs, tables, services, runtime ownership

### 6. Architecture Review
- One-click OS review: coupling, cycles, layering, security, scalability, maintainability…
- Findings attach to Twin nodes; click → open entity

### 7. Build Replay
- Requirements → Architecture → Database → Backend → Frontend → Tests → Reviews → Refactors → Current State
- Play evolution over twin kinds

### 8. Command Center
- Global palette: Explain, Review, Simulate, Diagram, Dead Code, Knowledge, Runtime, Replay, Teach, Coding, Twin Explorer

### 9. Interactive Learning
- Explain, animate execution, tutorial, quiz, safe simulate (no code changes)

### 10. Mission Control
- Workspace · Harness · Runtime · Twin · Architecture · Agents · Knowledge · Git · Sync — synchronized in real time

## Code map

```
static/js/living/
  api.js              # Twin / OS / Workspace client
  shell.js            # All 10 views + detail explain
  canvas.js           # Live Architecture Canvas
  command-center.js   # ⌘K palette
  styles.css
  index.js

static/js/coding/
  mode.js             # Universal Explain + X-Ray
  ...

routes/
  semantic_twin_routes.py
  spark_os_routes.py
  workspace_routes.py

docs/LIVING_WORKSPACE.md   # this file
```

## APIs used

| Capability | Endpoint family |
|------------|-----------------|
| Graph / explain / story / quiz | `/api/semantic-twin/*` |
| Review / timeline / runtime viz / memory | `/api/os/*` |
| Workspace / ensure twin / files | `/api/workspaces/*` |
| Host runtime telemetry | `/api/runtime` |
| Harness engines | `/api/harness/*` |

## How to try

1. Open **Mission Control** → select workspace → **Ensure Twin**
2. **Architecture** → click a node → detail panel
3. **⌘K** → Review Architecture / Teach This Component
4. Coding Mode → toggle **X-Ray** → move cursor over symbols
5. Select a symbol → Universal Explain panel (Twin, not raw LLM-on-source)
)
