# Spark Claude Code Integration

This directory contains the Claude Code skill bundle for Spark.

## User Flow

1. Open Spark Settings > Integrations.
2. Add a Claude Agent.
3. Copy the full setup commands shown after the generated token.
4. Toggle the tools Claude is allowed to use.
5. Configure the terminal Claude Code session:

```bash
export SPARK_URL=http://your-spark-host:7000
export SPARK_API_TOKEN=ody_generated_token
mkdir -p ~/.claude
curl -fsSL -H "Authorization: Bearer $SPARK_API_TOKEN" "$SPARK_URL/api/claude/plugin.zip" -o /tmp/spark-claude-skill.zip
python3 -m zipfile -e /tmp/spark-claude-skill.zip ~/.claude/
```

Claude Code auto-loads anything under `~/.claude/skills/`, so the `spark` skill is
available in any session that has `SPARK_URL` and `SPARK_API_TOKEN` in its
environment.

## What's in the bundle

- `skills/spark/SKILL.md` — the skill definition Claude Code reads.
- `skills/spark/scripts/spark_api.py` — small helper that calls the scoped
  `/api/codex/*` endpoints (these are the canonical scope-gated agent API; the
  `codex` path is historic and shared by all agent integrations).

## Scope enforcement

The token is scope-gated. Every tool surface is checked server-side in Spark,
so even if Claude tries to call a forbidden endpoint, it gets `403` until the
user enables the matching toggle in Settings > Integrations > Claude Agent.
