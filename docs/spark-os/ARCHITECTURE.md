# Spark Software Operating System — Phase 2 Architecture

> **Canonical model:** Semantic Twin  
> **Principle:** No duplicate representations. All capabilities read/write through the Twin graph.  
> **Scale target:** Organization-wide multi-project semantic memory + live runtime

---

## 1. Overall System Architecture

Spark OS sits **above** the existing Semantic Twin subsystem. Source code, runtime, agents, simulations, reviews, and marketplace blueprints are projections of and subscribers to the Twin.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Spark Software OS (Phase 2)                 │
│  Architecture │ Requirements │ Review │ Agents │ Time Machine   │
│  Simulation   │ Org Memory   │ Runtime Viz │ Marketplace │ Refactor│
└───────────────────────────────┬─────────────────────────────────┘
                                │ Twin-native APIs only
┌───────────────────────────────▼─────────────────────────────────┐
│              Semantic Twin (Phase 0–1) — CANONICAL              │
│  Graph │ Pipeline │ Storage │ Sync │ Timeline │ Runtime Events  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│  Spark Runtime │ Agent Framework │ Multi-model Inference        │
└─────────────────────────────────────────────────────────────────┘
```

### Invariants

1. **Twin is source of truth** for architecture, requirements, provenance, deps.  
2. **Code is a compiled view** of architecture nodes when architecture-first mode is active.  
3. **Agents never own private code models** — they own semantic regions (node id sets).  
4. **Simulations are pure** — no disk writes to project source.  
5. **Org memory is anonymizable** — no secrets cross project boundary without scrub.

---

## 2. Subsystem Diagrams

### 2.1 Architecture-First

```
Architecture Designer → Architecture Spec (nodes/edges)
        ↓ compile
   Code Scaffold (write_file via agent) + Twin generate/update
        ↓ continuous sync
   Twin graph ↔ Architecture Spec (bidirectional delta)
```

### 2.2 Living Requirements

```
Requirement Graph ──satisfies──► Components / APIs / Tables / Tests / Deploy
       ▲                              │
       └── generated_from ◄── Prompt / Decision / Plan
```

### 2.3 Review → Twin

```
Review Engine ──reads──► Twin graph metrics
       │
       └── writes review nodes + edges (related_to / decided_by)
```

### 2.4 Multi-Agent

```
Agent Workspace Bus (intents, claims, approvals)
        ↕
  Twin semantic regions (ownership attributes)
```

### 2.5 Time Machine / Simulation / Refactor

```
Timeline snapshots → scrub UI
Simulation: clone twin subgraph → hypothetical edges → report (no code write)
Refactor: analyze → simulate → review → migrate plan → validate → twin update
```

---

## 3. Folder Structure

```
services/spark_os/
  service.py                 # SparkOSService facade
  models.py                  # shared data models
  events.py                  # OS-wide event model
  architecture/              # Cap 1
  requirements/              # Cap 2
  review/                    # Cap 3
  agents/                    # Cap 4
  timemachine/               # Cap 5
  simulation/                # Cap 6
  memory/                    # Cap 7
  runtime/                   # Cap 8
  marketplace/               # Cap 9
  refactor/                  # Cap 10
  storage/                   # OS-side JSON stores

routes/spark_os_routes.py
static/js/spark-os/
docs/spark-os/
tests/test_spark_os/
data/spark_os/               # runtime persistence
```

---

## 4–8. Implementation surfaces

| Cap | Backend | Twin integration | API prefix |
|-----|---------|------------------|------------|
| Architecture-first | `architecture/*` | design nodes + compile → generate | `/api/os/architecture` |
| Living requirements | `requirements/*` | requirement edges + trace | `/api/os/requirements` |
| Design review | `review/*` | review finding nodes | `/api/os/review` |
| Multi-agent | `agents/*` | ownership attrs + intent bus | `/api/os/agents` |
| Time machine | `timemachine/*` | Phase-1 timeline + enrichment | `/api/os/timeline` |
| Simulation | `simulation/*` | graph-only impact | `/api/os/simulate` |
| Org memory | `memory/*` | pattern retrieval at generate | `/api/os/memory` |
| Runtime viz | `runtime/*` | Phase-1 runtime events → frames | `/api/os/runtime` |
| Marketplace | `marketplace/*` | seed twins / blueprints | `/api/os/marketplace` |
| Refactor | `refactor/*` | pipeline + twin update | `/api/os/refactor` |

---

## 9. Event Model

OS events (append-only log per project):

| Event | Payload |
|-------|---------|
| `arch.designed` | architecture_id, node_count |
| `arch.compiled` | twin_id, files |
| `req.linked` | requirement_id, artifact_id |
| `review.completed` | review_id, scores |
| `agent.intent` | agent, region, intent |
| `agent.approved` | intent_id |
| `sim.completed` | simulation_id, risk |
| `refactor.proposed` | plan_id |
| `runtime.frame` | frame for viz |
| `memory.learned` | pattern_id |

---

## 10. Storage Architecture

```
data/spark_os/
  architectures/{id}.json
  agent_workspaces/{project_id}.json
  simulations/{id}.json
  refactors/{id}.json
  org_memory/
    patterns.jsonl
    anti_patterns.jsonl
    incidents.jsonl
  marketplace/          # may mirror package seeds
  events/{project_id}.jsonl
```

Twin packages remain in `data/semantic_twins/` (unchanged).

---

## 11. Runtime Architecture

```
Browser Explorer / OS UI
    │ REST/SSE
Spark OS Service
    │
    ├─► SemanticTwinService (load/update/api)
    ├─► IntegrationService (registry, timeline, runtime)
    └─► OS stores (JSONL)
```

---

## 12. Agent Communication Protocol

Messages on the Twin bus:

```json
{
  "id": "...",
  "from_agent": "architect",
  "to_agent": "backend|broadcast",
  "type": "claim|delegate|negotiate|approve|reject|info",
  "region_node_ids": ["..."],
  "payload": {},
  "requires_approval": true,
  "ts": 0
}
```

Ownership: `node.attributes.owner_agent = "backend"`.

---

## 13. Synchronization Strategy

| Direction | Mechanism |
|-----------|-----------|
| Arch → Code | Compiler emits scaffold; agent/write_file; twin generate |
| Code → Arch | Continuous sync + arch extract from twin kinds |
| Runtime → Twin | RuntimeEventIngestor (Phase 1) + viz frames |
| Review → Twin | Finding nodes + related_to edges |
| Memory → Generate | Pre-generate retrieval injects into manifest metadata |

---

## 14. Scalability Plan

- Twin remains sharded per project (Phase 0 design).  
- Org memory is global JSONL with future vector index.  
- Simulations operate on in-memory twin clones.  
- Agent bus is per-project; fan-out O(agents × messages).  
- Marketplace catalog is static + cached.

---

## 15. Extension / Plugin Model

Implements Phase-1 protocols:

- `ArchitectureReviewExtension` → Review Engine  
- `RefactorExtension` → Refactor Pipeline  
- `MultiAgentCollabExtension` → Agent Workspace  
- `EditableTwinExtension` → Architecture Designer  
- `CrossProjectSearchExtension` → Org Memory search  

---

## Incremental Roadmap

| Slice | Deliverable |
|-------|-------------|
| 2.0 | This OS shell + all 10 engines (deterministic heuristics) |
| 2.1 | Visual architecture editor UI polish |
| 2.2 | LLM-augmented review/refactor narratives |
| 2.3 | Cross-org memory vector retrieval |
| 2.4 | Full multi-agent orchestration in agent_loop |
