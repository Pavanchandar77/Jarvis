# Spark × OpenCode Integration Strategy

> **Status:** Phase A0 + A implemented (Harness Layer + OpenCodeHarness)  
> **Principle:** OpenCode is Spark’s coding engine; Spark is not a fork of OpenCode  
> **Upstream:** `anomalyco/opencode` (MIT), monorepo under `opencode/` in this workspace  
> **Refinement:** Spark never talks to OpenCode directly — only via Harness Manager + Workspace Manager  
> See also: [HARNESS.md](./HARNESS.md)

## Architecture (refined)

```
Spark
  → Workspace Manager  (manifest, twin, runtime, memory, agents)
  → Harness Manager    (generic coding engine API)
  → OpenCodeHarness    (first implementation)
  → OpenCode (upstream, unmodified core)
       ↖ spark-opencode-plugin (out-of-tree)
```

Future harnesses (Claude Code, Codex) register the same `CodingHarness` interface.


---

## 1. Repository Analysis

### 1.1 What OpenCode is

OpenCode is a large **Bun monorepo** (Turbo + Effect) for an AI coding agent with:

| Surface | Package(s) | Role |
|---------|------------|------|
| Coding agent core | `packages/opencode` | Tools, sessions, providers, LSP, MCP, CLI, HTTP server |
| Domain core | `packages/core` | FS, DB, project, ripgrep, shared Effect services |
| LLM protocol | `packages/llm` | Provider adapters (OpenAI, Anthropic, Bedrock, xAI, …) |
| Plugin SDK | `packages/plugin` | **Primary extension surface** (v1 Hooks + v2 Effect API) |
| HTTP API | `packages/server`, `packages/opencode/.../httpapi` | Session, file, provider, PTY, workspace routes |
| Client SDK | `packages/client`, `packages/sdk`, `packages/sdk-next` | Network + **embedded in-process** host |
| TUI / Desktop / Web | `packages/tui`, `desktop`, `app` | User interfaces |
| Protocol/schema | `packages/protocol`, `packages/schema` | Shared contracts |

Runtime language stack: **TypeScript + Bun + Effect**, not Python.

### 1.2 What OpenCode already owns (do not reimplement)

- Repository / file edit: `write`, `edit`, `apply_patch`, `read`, `glob`, `grep`
- Terminal / shell: `shell` + PTY routes
- Git / worktree / control-plane workspace adapters
- Session management, compaction, system context epochs (`CONTEXT.md`)
- LSP integration (`packages/opencode/src/lsp`)
- MCP client
- Multi-agent (built-in agents, subagents, permissions)
- Provider catalog + multi-backend LLM routing (`packages/llm`, `provider/`)
- Desktop + TUI IDE surfaces
- Plugin loading from config + `{plugin,plugins}/*.{ts,js}` discovery

### 1.3 Extension surfaces (cleanest attachment points)

**A. Plugin Hooks (v1) — highest leverage, zero core edits**

From `@opencode-ai/plugin` `Hooks`:

| Hook | Spark use |
|------|-----------|
| `tool` | Register `semantic.*`, `runtime.*`, `architecture.*`, `simulation.*`, `knowledge.*` |
| `tool.execute.after` | Detect write/edit/patch → notify Semantic Twin |
| `tool.execute.before` | Optional policy / workspace fencing |
| `provider` / `auth` | Advertise Spark as a model provider |
| `chat.params` / `chat.headers` | Inject Spark routing metadata / auth to Spark Runtime |
| `experimental.chat.system.transform` | Inject twin summary / org memory snippets |
| `event` | Forward OpenCode bus events into Spark event log |
| `config` | Normalize paths, Spark base URL |

**B. Plugin v2 Effect API** (`@opencode-ai/plugin/v2/effect`)

- `ctx.catalog.transform` — inject Spark models into provider catalog  
- `ctx.aisdk.sdk` / `ctx.aisdk.language` — **route inference through Spark** without core forks  
- `ctx.agent.transform` / `ctx.skill.transform` — Spark-aware agents/skills  
- `ctx.command.transform` — Spark slash commands  

**C. HTTP API / SDK**

- Run OpenCode server (`opencode serve` / embedded `sdk-next`)  
- Spark adapter calls OpenCode sessions, files, PTY as a **client**  
- `sdk-next` Embedded OpenCode: in-process host without network (advanced path)

**D. Config / plugins directory**

- Project or global OpenCode config: `plugin: ["file:///…/spark-opencode-plugin"]`  
- Auto-discover `plugin/*.ts` under project (see `config/plugin.ts`)

**E. MCP (secondary)**

- Spark can expose MCP tools; OpenCode already has MCP client  
- Prefer first-class plugin tools for latency and UX; MCP as fallback for external hosts

### 1.4 How Spark already relates to OpenCode

- `ACKNOWLEDGMENTS.md` / `licenses/opencode-MIT-LICENSE.txt`: Spark **already borrowed** agent-loop / tool-execution **patterns** — not a runtime dependency today.  
- `integrations/codex` and `integrations/claude`: precedent for **out-of-tree agent plugins** talking to Spark/Spark via HTTP + API tokens.  
- Semantic Twin Phase 1: `on_file_written` / `on_agent_turn_end` for Spark’s own agent tools — same lifecycle can be driven from OpenCode plugin hooks.  
- Spark Runtime: model discovery, endpoints, cookbook serve — natural **provider backend** for OpenCode.

### 1.5 Impedance mismatch (must design for)

| Concern | OpenCode | Spark |
|---------|----------|-------|
| Language | TypeScript / Bun / Effect | Python / FastAPI / Electron |
| Process | Own server + TUI/desktop | App orchestrator + local LLM |
| Coding tools | Native write/edit/shell/LSP | `write_file`/`edit_file` in agent loop |
| Inference | Direct provider SDKs | Centralized runtime + settings |
| Project model | Location / worktree / session | Project registry + Semantic Twin |

**Conclusion:** Integration must be **process-boundary adapters + OpenCode plugins**, not a Python rewrite of OpenCode and not a fork of OpenCode core.

---

## 2. Integration Strategy (Recommended)

### 2.1 Roles

```
┌──────────────────────────────────────────────────────────────┐
│                         SPARK                                │
│  Runtime │ Semantic Twin │ OS │ Agents │ Memory │ Models     │
│                          │                                   │
│                 OpenCode Adapter (Python)                    │
│            process mgmt · session bridge · twin sync         │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / env / plugin config
┌──────────────────────────▼───────────────────────────────────┐
│              OPENCODE (unmodified upstream tree)             │
│  sessions · tools · git · shell · LSP · TUI/desktop          │
│                          │                                   │
│              spark-opencode-plugin (TS, out-of-tree)         │
│     tools · provider bridge · tool.execute.after → Spark     │
└──────────────────────────────────────────────────────────────┘
```

- **OpenCode** = coding engine (edit, git, terminal, sessions, IDE).  
- **Spark** = platform (twin, runtime, memory, review, simulation, scheduling).  
- **spark-opencode-plugin** = only code that “lives inside” OpenCode’s plugin loader (still **not** upstream core).  
- **services/opencode_adapter** = Spark-side control plane.

### 2.2 Strategy name: **Plugin + Sidecar Adapter**

1. Keep `opencode/` as an **upstream-trackable subtree** (git submodule preferred long-term).  
2. Ship `integrations/opencode/plugin/` (TypeScript) registered via OpenCode config.  
3. Ship `services/opencode_adapter/` (Python) to start/stop OpenCode, map sessions, fan out twin updates.  
4. Point OpenCode inference at Spark via **OpenAI-compatible** endpoint already exposed by Spark **or** provider hook that rewrites base URL to Spark Runtime.  
5. Twin updates: plugin after write/edit → `POST /api/semantic-twin/...` / integration hooks.  

### 2.3 Alternatives considered (not primary)

| Approach | Verdict |
|----------|---------|
| Fork OpenCode into Spark agent loop | High maintenance; rejected |
| Rewrite OpenCode tools in Python | Duplicates LSP/git/shell; rejected |
| MCP-only bridge | Works but weaker UX; keep as secondary |
| Embed OpenCode via sdk-next in Electron | Powerful later; higher coupling; Phase C |

---

## 3. Extension Points (Concrete)

### 3.1 File / twin sync

Intercept in plugin:

```
tool.execute.after
  tools: write | edit | apply_patch | (optional) shell when mutating
  → extract paths from args/metadata
  → POST Spark: /api/opencode/sync or reuse twin continuous sync
```

Prefer reusing Phase-1 `ContinuousSync` + project registry keyed by OpenCode `directory` / worktree.

### 3.2 Inference through Spark Runtime

**Preferred (no OpenCode edit):**

1. Configure OpenCode provider as OpenAI-compatible pointing at Spark  
   e.g. `http://127.0.0.1:<spark>/v1` (or existing endpoint resolver).  
2. Or plugin `provider` + v2 `aisdk.language` to force Spark base URL and inject `X-Spark-Session` headers.

OpenCode must not hold provider API keys for models Spark already manages when running under Spark.

### 3.3 Spark tools as OpenCode tools

Plugin `tool: { "semantic_search": {...}, ... }` implementations HTTP-call:

| OpenCode tool name | Spark backend |
|--------------------|---------------|
| `semantic_search` | TwinApiFacade.search / `/api/semantic-twin/{id}/search` |
| `semantic_explain` | explain |
| `semantic_trace_execution` | traceExecution |
| `semantic_trace_dependency` | traceDependency |
| `semantic_find_concept` | findConcept |
| `runtime_select_model` | model routes / settings |
| `runtime_load_model` | cookbook/hwfit serve if applicable |
| `architecture_review` | `/api/os/review/{twin_id}` |
| `simulation_run` | `/api/os/simulate/{twin_id}` |
| `knowledge_search` | `/api/os/memory/search` |

Names can be namespaced (`spark_semantic_search`) to avoid collisions.

### 3.4 Session bridge

Adapter maps:

```
Spark session_id  ↔  OpenCode sessionID
Spark workspace   ↔  OpenCode Location.directory / worktree
Spark owner       ↔  API token / auth middleware
```

OpenCode remains source of truth for coding transcripts; Spark stores twin + project registry links.

### 3.5 Events

```
OpenCode plugin event hook
  → Spark adapter /api/opencode/events
  → OSEventLog + optional twin runtime ingest
```

Useful events: session start/end, tool results, permission prompts (for UI).

### 3.6 Learning mode

On successful mutating tools (debounced end of turn / session idle):

1. Incremental twin update (dirty files)  
2. Optional full finalize if new project  
3. Emit SSE `semantic_twin` to Spark UI  
4. Link explorer `/semantic-twin?twin=` + `/spark-os?twin=`

---

## 4. Adapter Architecture

```
services/opencode_adapter/
  __init__.py
  adapter.py          # OpenCodeAdapter facade (start/stop/status)
  session.py          # session mapping + prompt relay
  tools.py            # Spark tool registry docs for plugin manifest
  events.py           # inbound OpenCode event normalization
  sync.py             # twin incremental update from file events
  process.py          # spawn opencode serve / healthcheck
  config.py           # generate opencode config + plugin path
  auth.py             # short-lived tokens for plugin → Spark

integrations/opencode/
  README.md
  plugin/             # TypeScript OpenCode plugin (upstream-compatible)
    package.json
    src/index.ts      # Hooks: tools, provider, tool.execute.after
    src/spark-client.ts
    src/twin-sync.ts
    src/tools/*.ts
  config/
    opencode.spark.jsonc.example

routes/opencode_routes.py   # /api/opencode/* control + plugin callbacks
docs/opencode-integration/  # this strategy + upgrade runbook
```

### 4.1 Adapter interface (Spark-facing)

```python
class OpenCodeAdapter(Protocol):
    async def start(self, workspace: str, *, owner: str | None) -> EngineHandle
    async def stop(self, handle: EngineHandle) -> None
    async def create_session(self, handle, prompt: str, model: str | None) -> SessionRef
    async def send(self, session: SessionRef, message: str) -> None
    async def stream_events(self, session: SessionRef) -> AsyncIterator[OCEvent]
    async def status(self, handle) -> EngineStatus
```

Internally: HTTP to OpenCode server (Phase A) or sdk-next embed (Phase C).

### 4.2 Plugin → Spark interface

```
POST /api/opencode/plugin/file-changed
  { workspace, paths[], session_id, tool, diff? }

POST /api/opencode/plugin/tools/*
  proxy to Twin / OS / Runtime

GET  /api/opencode/plugin/models
  catalog from Spark model discovery

POST /api/opencode/plugin/chat/complete   # optional if not using OpenAI-compat path
```

Auth: `X-API-Key` / bearer scoped token (mirror codex integration).

---

## 5. File-by-File Implementation Plan

### Phase A — Zero OpenCode core edits (recommended start)

| File / area | Action |
|-------------|--------|
| `services/opencode_adapter/*` | **Create** Spark-side adapter |
| `routes/opencode_routes.py` | **Create** control + plugin callback API |
| `app.py` | **Wire** router + process lifecycle |
| `src/constants.py` | **Add** `OPENCODE_DIR`, adapter data paths |
| `integrations/opencode/plugin/*` | **Create** TS plugin package |
| `integrations/opencode/README.md` | Install: point OpenCode config at plugin |
| `docs/opencode-integration/*` | Strategy + upgrade runbook |
| `tests/test_opencode_adapter/*` | Adapter + sync unit tests (mock OpenCode) |
| `opencode/**` | **No modifications** |

### Phase B — Hardening

| File / area | Action |
|-------------|--------|
| Adapter `process.py` | Health, restart, version pin |
| Plugin twin-sync | Debounce, rename/delete detection |
| Plugin system transform | Inject twin learning snippets |
| Spark UI | “Open in OpenCode” / engine status tile |
| Agent bridge | Document when Spark agent vs OpenCode engine |

### Phase C — Optional advanced (still avoid core forks)

| File / area | Action |
|-------------|--------|
| Adapter embed path | Evaluate `sdk-next` Embedded OpenCode from a Node/Bun sidecar |
| Desktop | Launch OpenCode desktop with Spark env |
| Provider catalog transform | v2 Effect plugin for Spark model list |

### Only if no alternative (document as divergence)

| Change | Why it would be needed | Mitigation first |
|--------|------------------------|------------------|
| Patch provider to force all traffic through Spark | Some providers bypass OpenAI-compat | Prefer aisdk hooks + config |
| Patch write tool to emit custom event | after-hook insufficient | Use `tool.execute.after` + metadata from write |
| Pin forked commit | Upstream breaks plugin API | Version-lock plugin peer deps; dual-support adapters |

---

## 6. Required Modifications

### 6.1 OpenCode tree

**None required for Phase A.**

OpenCode remains a vendored/submodule upstream copy used as:

- binary / `bun run` entry  
- documentation reference  
- optional local plugin resolution path

### 6.2 Spark tree (required)

1. Adapter service + routes  
2. Out-of-tree OpenCode plugin  
3. Auth token path for plugin callbacks  
4. Twin sync entry that reuses Phase-1 continuous sync  
5. Config generator writing OpenCode `plugin` + Spark provider endpoint  

### 6.3 Runtime configuration (user/machine)

Example OpenCode config fragment (generated, not hand-edited core):

```jsonc
{
  "plugin": [
    ["file:///path/to/spark/integrations/opencode/plugin", {
      "sparkUrl": "http://127.0.0.1:7000",
      "token": "ody_...",
      "twinProjectId": "optional"
    }]
  ],
  "provider": {
    /* Spark-backed openai-compatible entry */
  }
}
```

---

## 7. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| OpenCode plugin API churn (v1→v2) | High | Isolate plugin behind thin interface; support v1 hooks first; track `dev` branch |
| Dual coding engines (Spark agent + OpenCode) confuse users | Medium | Product rule: OpenCode = code engine when enabled; Spark agent for non-code |
| Twin double-updates (Spark write_file + OpenCode write) | Medium | Single workspace owner; debounce by path hash |
| Inference loops / auth leakage | High | Scoped tokens; no long-lived provider keys in plugin |
| Process weight (Bun + Python + Electron) | Medium | Lazy-start OpenCode only when coding session opens |
| Submodule drift / large repo size | Medium | Submodule + sparse checkout docs; CI pin commit SHA |
| Windows path / file URL plugin loading | Medium | Adapter generates `file://` URLs correctly on Win |
| Shell mutations miss twin sync | Medium | Heuristic path parse + optional full scan on session end |
| License compliance | Low | MIT — preserve notices (already in licenses/) |

---

## 8. Migration Strategy

### Current state

- Spark agent loop is the default coding path (`write_file` / `edit_file`).  
- OpenCode exists as a **cloned monorepo**, not yet a runtime dependency.  
- Patterns only (ACKNOWLEDGMENTS).

### Migration steps

1. **Pin** OpenCode commit SHA; document Bun version from `packageManager`.  
2. **Ship adapter + plugin** without removing Spark agent tools.  
3. **Feature flag** `opencode_engine_enabled` (settings).  
4. **Pilot**: code-mode sessions optionally spawn OpenCode with workspace = project dir.  
5. **Parity**: twin + learning mode works for OpenCode writes.  
6. **Default flip** (later): code-mode → OpenCode engine; Spark agent retains orchestration/non-code.  
7. **Deprecate** only duplicate low-level file tools if product requires — not required for integration.

No big-bang cutover.

---

## 9. Upstream Compatibility Plan

### 9.1 Golden rules

1. **Never edit** `opencode/packages/opencode/src/**` for Spark features.  
2. All Spark behavior in `integrations/opencode/plugin` + `services/opencode_adapter`.  
3. Track upstream with **submodule** or `git subtree` + pin file `integrations/opencode/UPSTREAM_SHA`.  
4. CI job: plugin typecheck against pinned OpenCode `plugin` package exports.  
5. On upgrade: run plugin tests + smoke `opencode serve` + one write → twin update.

### 9.2 Upgrade procedure

```
1. Update opencode pin to new upstream tag/commit
2. bun install in opencode/
3. Rebuild/typecheck spark plugin against @opencode-ai/plugin
4. Diff Hooks / v2 Effect API for breaks
5. Fix only integrations/opencode/plugin
6. Run Spark adapter integration tests
7. Record changelog of plugin API deltas
```

### 9.3 What we will never do without an ADR

- Patching OpenCode session LLM core  
- Replacing OpenCode tool registry  
- Merging OpenCode UI into Spark’s static SPA as a fork  
- Copying large OpenCode packages into `src/`

### 9.4 Compatibility matrix (maintain)

| OpenCode version | Plugin API | Spark adapter |
|------------------|------------|---------------|
| pinned SHA | v1 Hooks | Phase A |
| next | v1 + v2 Effect | Phase B |

---

## 10. Incremental Implementation Roadmap

### Phase 0 — Analysis (this document)

- [x] Repo map, extension points, strategy  
- [x] Risks, migration, upstream plan  

### Phase A — Minimal viable bridge (1–2 weeks eng)

1. `services/opencode_adapter` process + health  
2. `routes/opencode_routes` plugin callbacks  
3. TS plugin: `tool.execute.after` → file-changed  
4. Twin continuous sync for OpenCode workspace  
5. OpenAI-compatible inference via Spark endpoint  
6. Docs: enable flag + config generation  
7. Tests with mocked OpenCode HTTP  

**Exit criteria:** Edit file in OpenCode → twin updates; chat uses Spark models.

### Phase B — Capability parity (2–4 weeks)

1. Full Spark tool surface in plugin  
2. System context inject (twin summary / org memory)  
3. Session mapping in project registry  
4. Learning mode SSE + explorer links  
5. Architecture review / simulation tools  
6. Permission-aware auth tokens  

**Exit criteria:** Agent can code in OpenCode while calling semantic/review/simulate tools.

### Phase C — Product polish

1. UI: engine selector, OpenCode status  
2. Optional sdk-next embed evaluation  
3. Desktop deep-link  
4. Automated upstream upgrade CI  

### Phase D — Optional deeper bind (only if needed)

1. v2 Effect catalog transform for live model list  
2. Shared PTY environment from Spark  
3. Worktree control-plane alignment  

---

## Recommended First Code Slice (when implementation starts)

**Do not modify OpenCode core.**

Implement only:

1. `services/opencode_adapter/` (Python)  
2. `integrations/opencode/plugin/` (TypeScript, uses public `@opencode-ai/plugin` types)  
3. `routes/opencode_routes.py`  
4. Wire twin sync to existing Phase-1 `ContinuousSync`  

Success metric: **zero lines changed under `opencode/packages/**` except dependency lock if required for local plugin resolution.**

---

## Decision Summary

| Question | Decision |
|----------|----------|
| Is Spark a fork of OpenCode? | **No** |
| Primary extension mechanism? | **OpenCode Plugin (hooks) + Spark adapter** |
| Inference? | **Spark Runtime via OpenAI-compat / provider hooks** |
| Twin updates? | **tool.execute.after → ContinuousSync** |
| When to edit OpenCode core? | **Never in Phase A–C; ADR-only later** |
| Relationship to existing Spark agent? | **Parallel engines; OpenCode = coding specialist** |

---

*Next step when approved: implement Phase A only, keeping `opencode/` upstream-clean.*
