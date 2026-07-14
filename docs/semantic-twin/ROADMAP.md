# Semantic Twin — Implementation Roadmap

See §12 of [ARCHITECTURE.md](./ARCHITECTURE.md) for the full phased plan.

## Current milestone: Phase 1 Integration

Phase 0 foundation + Phase 1 automatic lifecycle:

- Agent turn hooks auto-generate/update twins after `write_file` / `edit_file`
- Expanded `GenerationManifest` preserves AI intent
- Project registry + explorer project list
- Continuous sync, runtime events, version timeline
- Agent tool `semantic_twin`
- Extension point protocols

See [PHASE1.md](./PHASE1.md).

## Phase 2 delivered

Spark Software OS — see `docs/spark-os/ARCHITECTURE.md` and `services/spark_os/`.

Capabilities: architecture-first, living requirements, design review, multi-agent
workspace, time machine, simulation, org memory, runtime viz, marketplace,
autonomous refactoring — all via Semantic Twin.

## Next up (Phase 2.x / 3)

1. Tree-sitter ASTs, richer call/dataflow
2. Vector search for org memory / concepts
3. LLM-augmented review narratives
4. Visual architecture editor polish

