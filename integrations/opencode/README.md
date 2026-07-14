# OpenCode Harness (Spark)

OpenCode is Spark’s **first coding engine** via the Harness Layer.

```
Spark → Workspace Manager → Harness Manager → OpenCodeHarness → OpenCode
```

Spark never imports OpenCode packages. OpenCode core is **never modified**.

## Layout

| Path | Role |
|------|------|
| `services/harness/` | Generic harness interface + manager |
| `services/workspace/` | Workspace manifest + project ownership |
| `services/harness/opencode_harness.py` | OpenCode implementation |
| `integrations/opencode/plugin/` | Out-of-tree OpenCode plugin |
| `opencode/` | Upstream monorepo (pin only) |
| `UPSTREAM_SHA` | Pinned commit for upgrades |

## Enable

1. Create a workspace via `POST /api/workspaces` with `repo_root` + optional `active_harness: "opencode"`.
2. `POST /api/workspaces/{id}/harness/start`.
3. OpenCode config is generated under `{repo}/.spark/harness/opencode/opencode.spark.json`.
4. Point OpenCode at that plugin (or load the plugin path from the generated file).

## Plugin options

```json
{
  "sparkUrl": "http://127.0.0.1:7000",
  "token": "<api token>",
  "workspaceId": "<workspace_id>",
  "twinId": "<optional>"
}
```

## Upstream rule

**No patches under `opencode/packages/**` for Spark features.**  
If a patch becomes unavoidable, document it in `UPSTREAM_PATCHES.md` with justification and removal criteria.

## Upgrade OpenCode

```
1. Update opencode/ to new commit; write SHA to UPSTREAM_SHA
2. Typecheck integrations/opencode/plugin against @opencode-ai/plugin
3. Run tests/test_harness tests/test_workspace
4. Smoke: start harness → write file → twin sync via /api/harness/file-changed
```
