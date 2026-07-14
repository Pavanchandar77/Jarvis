# Spark Semantic Twin — Production Architecture

> **Status:** Production-ready subsystem design & implementation  
> **Audience:** Principal engineers, platform owners, plugin authors  
> **Scale target:** Millions of generated applications, concurrent explorers

---

## 1. Overall Architecture

The **Semantic Twin** is a second-class artifact produced *atomically* with every Spark-generated application. It is a **structured knowledge system** — a multi-graph over code, intent, provenance, runtime, and pedagogy — that powers an interactive frontend. It is **not** documentation, comments, or markdown.

### Design principles

| Principle | Implication |
|-----------|-------------|
| **Graph-native** | All knowledge is nodes + typed edges. Prose is a *view*, never the source of truth. |
| **Provenance-first** | Every node answers: who created it, which prompt, which decision, which alternatives. |
| **Multi-audience** | One node, seven viewing modes (Beginner → Security). |
| **Living system** | Click → animate Prompt → Requirement → Decision → Code → Runtime → Deps → Concepts. |
| **Incremental** | File-level dirty-set patches; never full rebuild on one-line edits at scale. |
| **Extensible** | Language parsers, concept taxonomies, and view renderers are plugins. |
| **Multi-tenant safe** | Twin ownership follows application ownership; all APIs are owner-scoped. |

### Pipeline (mandatory order)

```
Source Tree + Generation Manifest
  → Parser Layer
  → AST Extraction
  → Semantic Analyzer
  → Knowledge Graph Builder
  → Execution Analyzer
  → Concept Extractor
  → Relationship Engine
  → Twin Generator
  → Frontend API
```

### Runtime topology

```
Spark Generator ──emit──► Twin Pipeline (worker / inline)
                              │
                              ▼
                     Twin Repository (content-addressed shards)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         Graph Store     Adjacency Index   Full-text / Vector
                              │
                              ▼
                    Semantic Twin HTTP API → Explorer Frontend
```

---

## 2. Folder Structure

```
services/semantic_twin/          # backend pipeline + API
  models.py, schema.py, ids.py, service.py
  graph/  pipeline/  provenance/  api/  storage/  plugins/
routes/semantic_twin_routes.py
static/js/semantic-twin/         # living explorer
packages/semantic-twin-types/    # shared TS contracts
docs/semantic-twin/
tests/test_semantic_twin/
data/semantic_twins/             # runtime storage under DATA_DIR
```

---

## 3. Data Models

**SemanticTwin:** twin_id, application_id, schema_version, content_revision,
content_hash, owner, manifest, nodes, edges, indexes, meta.

**SemanticNode (every node):** id, kind, name, description, purpose, why_exists,
created_by, prompt_id, dependencies, dependents, source_file, source_location,
execution_order, related_concepts, suggested_improvements, learning_resources,
difficulty_score, views (7 modes), attributes.

**SemanticEdge:** id, kind, source, target, weight, attributes.

**GenerationManifest:** prompts, requirements, design decisions, alternatives,
file→prompt map, tech_stack, model_ids.

---

## 4. TypeScript Interfaces

Canonical: `packages/semantic-twin-types/index.ts`  
Python mirror: `services/semantic_twin/models.py`

Exports: `SemanticNode`, `SemanticEdge`, `SemanticTwin`, `ViewingMode`,
`GenerationManifest`, `TwinApi`, `AnimStep`, `StoryStage`, quiz/tutorial/
simulation/compare types.

---

## 5. Backend Implementation

`SemanticTwinService`:

- `generate(app_root, manifest)` — full pipeline
- `update(twin_id, changed_files)` — incremental
- `load` / `list` / `delete`
- `api(twin)` → `TwinApiFacade`

Pipeline stages implement `Stage.run(PipelineContext)`. Language plugins
provide parse/AST/symbols. Views composed deterministically (Phase 0).

---

## 6. Graph Schema

**Node kinds:** application, module, component, function, class, method, hook,
api_endpoint, state_*, route, page, table, column, event*, prompt, requirement,
design_decision, alternative, concept, test, security_surface, perf_hotspot, error, …

**Edge kinds:** contains, depends_on, imports, calls, renders, reads_state,
writes_state, routes_to, data_flows_to, fk_to, emits, handles, generated_from,
decided_by, alternative_to, related_to, illustrates.

**Invariants:** unique ids; edge endpoints exist; `contains` acyclic; `calls`
may cycle; path safety for source_file.

See `GRAPH_SCHEMA.md`.

---

## 7. Frontend Architecture

Vanilla ES modules (Spark convention):

| Module | Role |
|--------|------|
| api-client.js | REST wrappers |
| graph-renderer.js | Living graph + LOD |
| node-panel.js | Multi-mode panel |
| animation-pipeline.js | Story choreography |
| explorer.js | Shell: search, selection |

---

## 8. Animation Architecture

```
Prompt → Requirement → Design decision → Generated code
  → Runtime execution → Dependencies → Related concepts
```

`AnimationController`: play/pause/step/skip; respects `prefers-reduced-motion`;
runtime stage uses `traceExecution` frames.

---

## 9. Incremental Update Strategy

1. Hash files vs twin file index  
2. Dirty set = changed ∪ deleted ∪ reverse-import dependents  
3. Drop dirty nodes/edges; re-pipeline dirty files; rebind cross-file edges  
4. Stable concept ids by slug; delta journal  
5. Double-buffer write + atomic swap; `force_full` fallback  

---

## 10. Storage Format

```
data/semantic_twins/{twin_id}/
  twin.json
  graph/nodes.jsonl  graph/edges.jsonl
  indexes/*.json
  manifest/*
  deltas/{revision}.patch.json
```

Schema version `1.0.0`. Content-addressed `content_hash`.

---

## 11. Extension / Plugin System

Plugin types: Language, Concept, View, Analyzer, Export.  
`PluginRegistry` + built-ins: Python, TypeScript, Generic.  
Trusted in-process (Phase 0); sandbox later for third-party.

---

## 12. Implementation Roadmap

| Phase | Scope |
|-------|--------|
| **0** | Foundation (models, pipeline, API, explorer, storage) |
| **1** | Automatic generation, continuous sync, runtime, agent tool, registry, timeline — **delivered** (see PHASE1.md) |
| **2** | Tree-sitter, real call/dataflow, vectors, coverage |
| **3** | Workers, lazy subgraphs, SQLite for million-node twins |
| **4** | Product polish (quiz UX, simulate in editor, deeper timeline scrubber) |
| **5** | Public plugin SDK + export connectors |

### Phase 1 integration points

```
agent_loop.start  → on_agent_turn_start (ManifestBuilder)
write_file/edit   → on_file_written → ContinuousSync
agent_loop.end    → on_agent_turn_end → generate/update + ProjectRegistry + Timeline + SSE
```

---

## Performance budget (initial)

| Operation | Target |
|-----------|--------|
| Generate twin (1k files, Python) | < 30s p95 local |
| Incremental single-file update | < 500ms p95 |
| `search` | < 50ms p95 in-memory |
| Explorer first paint (5k nodes) | < 1s with LOD |
