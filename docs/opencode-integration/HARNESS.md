# Harness Layer + Workspace Manager (Phase A0 / A)

## Architecture

```
Spark subsystems (Twin, OS, Runtime, UI)
              │
              ▼
      Workspace Manager  ← owns project (manifest)
              │
              ▼
      Harness Manager    ← owns engines (generic)
              │
     ┌────────┼────────┐
     ▼        ▼        ▼
 OpenCode  Null    (Claude/Codex later)
 Harness   Harness
```

## Workspace Manifest

Canonical fields: `workspace_id`, `repo_root`, `runtime_profile`, `active_model`,
`twin_id`, `knowledge_memory_id`, `active_harness`, `harness_handle_id`,
`harness_session_id`, `active_agents`, `project_id`, VCS metadata.

Stored under `data/workspaces/manifests/{id}.json`.

**Rule:** Spark never reads OpenCode config as project truth.

## Harness interface

```
start / stop / create_session / send / stream / cancel / status
```

## APIs

| Prefix | Purpose |
|--------|---------|
| `/api/workspaces` | Workspace CRUD + harness start + twin bind |
| `/api/harness` | Plugin callbacks + tool invoke (engine-agnostic) |

## Phase A OpenCode

- Implementation: `services/harness/opencode_harness.py`
- Plugin: `integrations/opencode/plugin` (tool.execute.after → twin sync)
- Core patches: **none** (`UPSTREAM_PATCHES.md` empty)
