# Semantic Twin Phase 1 — Automatic Generation & Continuous Sync

## Goal

The Semantic Twin is an inseparable part of Spark’s generation lifecycle.
Code and Twin co-evolve; agents reason over the graph instead of re-parsing repos.

## Automatic flow

```
Prompt → Planning → Generation → Write Files
  → Generate/Update Semantic Twin → Register Project → Open /semantic-twin
```

Triggered by:

1. **Agent turn start** — `on_agent_turn_start` captures user prompt, plan, model, backend  
2. **write_file / edit_file success** — `on_file_written` tracks dirty files + continuous sync  
3. **Agent turn end** — `on_agent_turn_end` builds expanded `GenerationManifest`, calls
   `SemanticTwinService.generate` / `update`, registers project, records timeline, emits SSE

## Expanded GenerationManifest

Preserves AI intent (not only source):

- `user_prompt`, `planning_prompt`
- `agent_chain`, `tool_history`
- `backend`, `runtime_metadata`
- `file_ownership`, `component_ownership`
- `dependency_reasoning`, `trade_offs`
- plus Phase-0 fields (prompts, decisions, requirements, file_prompt_map, …)

## Continuous synchronization

```
File Saved → dirty set → debounced ContinuousSync → twin.update → timeline
```

Uses existing incremental pipeline; full rebuild only when needed.

## Runtime events

`POST /api/semantic-twin/{twin_id}/runtime` enriches existing nodes with:

- app.launch, route.execute, api.request, component.render
- state.transition, error, warning, perf.metric

## Agent tool

```semantic_twin``` actions: search, explain, trace_*, find_concept, simulate,
architecture, status, list_projects, quiz, tutorial, timeline.

## Projects UI

- `GET /api/semantic-twin/projects/list`
- Explorer loads registered projects automatically
- SSE `semantic_twin` + chat note with explorer link after generation

## Version timeline

`GET /api/semantic-twin/{twin_id}/timeline` (+ version + diff)

## Extension points

`services/semantic_twin/integration/extensions.py` — protocols for editable twins,
architecture review, refactor, repo ingest, cross-project search, multi-agent collab.
Not implemented; register via `EXTENSIONS`.

## Code map

| Concern | Module |
|---------|--------|
| Hooks | `integration/hooks.py` |
| Manifest builder | `integration/manifest_builder.py` |
| Project registry | `integration/project_registry.py` |
| Continuous sync | `integration/continuous_sync.py` |
| Runtime | `integration/runtime_events.py` |
| Timeline | `integration/version_timeline.py` |
| Agent tool | `integration/agent_bridge.py` |
| Extensions | `integration/extensions.py` |
