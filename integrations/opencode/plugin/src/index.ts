/**
 * Spark OpenCode Plugin
 *
 * Lives OUTSIDE OpenCode core. Loaded via OpenCode config:
 *   plugin: [["/path/to/integrations/opencode/plugin", { sparkUrl, token, workspaceId }]]
 *
 * Responsibilities:
 *  - Notify Spark Workspace Manager on write/edit/apply_patch
 *  - Register Spark tools (semantic / runtime / architecture / simulation / knowledge)
 *  - Optionally rewrite chat headers toward Spark Runtime
 *
 * Upstream rule: never import OpenCode internals — only @opencode-ai/plugin types.
 */

export type PluginOptions = {
  sparkUrl?: string
  token?: string
  workspaceId?: string
  twinId?: string
  owner?: string
  model?: string
}

type Hooks = {
  event?: (input: { event: unknown }) => Promise<void>
  tool?: Record<string, ToolDef>
  "tool.execute.after"?: (
    input: { tool: string; sessionID: string; callID: string; args: any },
    output: { title: string; output: string; metadata: any },
  ) => Promise<void>
  "chat.headers"?: (
    input: unknown,
    output: { headers: Record<string, string> },
  ) => Promise<void>
  "experimental.chat.system.transform"?: (
    input: { sessionID?: string; model: unknown },
    output: { system: string[] },
  ) => Promise<void>
}

type ToolDef = {
  description: string
  // parameters shape is engine-defined; keep loose for upstream compat
  parameters?: unknown
  execute: (args: any) => Promise<any>
}

const MUTATING = new Set(["write", "edit", "apply_patch", "Write", "Edit"])

async function sparkFetch(
  base: string,
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<any> {
  const res = await fetch(`${base.replace(/\/$/, "")}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}`, "X-API-Key": token } : {}),
      ...(init.headers || {}),
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`Spark ${res.status}: ${text}`)
  }
  return res.json()
}

function extractPaths(tool: string, args: any, metadata: any): string[] {
  const paths: string[] = []
  if (args?.filePath) paths.push(String(args.filePath))
  if (args?.path) paths.push(String(args.path))
  if (metadata?.filepath) paths.push(String(metadata.filepath))
  if (metadata?.filePath) paths.push(String(metadata.filePath))
  if (Array.isArray(metadata?.files)) {
    for (const f of metadata.files) paths.push(String(f))
  }
  // apply_patch may list files in output
  return [...new Set(paths.filter(Boolean))]
}

export const SparkPlugin = async (_ctx: unknown, options: PluginOptions = {}): Promise<Hooks> => {
  const sparkUrl = options.sparkUrl || process.env.SPARK_URL || "http://127.0.0.1:7000"
  const token = options.token || process.env.SPARK_TOKEN || process.env.SPARK_API_TOKEN || ""
  const workspaceId = options.workspaceId || process.env.SPARK_WORKSPACE_ID || ""
  const twinId = options.twinId || process.env.SPARK_TWIN_ID || ""

  const invoke = async (action: string, payload: Record<string, unknown> = {}) => {
    return sparkFetch(sparkUrl, "/api/harness/tools/invoke", token, {
      method: "POST",
      body: JSON.stringify({
        action,
        workspace_id: workspaceId || undefined,
        twin_id: twinId || undefined,
        payload,
      }),
    })
  }

  const tool = (action: string, description: string): ToolDef => ({
    description,
    execute: async (args: any) => {
      try {
        const result = await invoke(action, args || {})
        return { title: action, output: JSON.stringify(result, null, 2), metadata: { action } }
      } catch (err: any) {
        return { title: action, output: `Error: ${err?.message || err}`, metadata: { error: true } }
      }
    },
  })

  return {
    async "tool.execute.after"(input, output) {
      if (!MUTATING.has(input.tool) && !String(input.tool).toLowerCase().includes("write")) {
        return
      }
      if (!workspaceId) return
      const paths = extractPaths(input.tool, input.args, output.metadata)
      if (!paths.length) return
      try {
        await sparkFetch(sparkUrl, "/api/harness/file-changed", token, {
          method: "POST",
          body: JSON.stringify({
            workspace_id: workspaceId,
            paths,
            session_id: input.sessionID,
            tool: input.tool,
            harness_id: "opencode",
          }),
        })
      } catch (err) {
        // Non-fatal — coding must not fail if twin sync is down
        console.warn("[spark-plugin] file-changed failed", err)
      }
    },

    async "chat.headers"(_input, output) {
      // Route metadata so Spark Runtime can attribute traffic
      output.headers = {
        ...output.headers,
        "X-Spark-Workspace": workspaceId || "",
        "X-Spark-Harness": "opencode",
      }
      if (twinId) output.headers["X-Spark-Twin"] = twinId
    },

    async "experimental.chat.system.transform"(_input, output) {
      output.system.push(
        [
          "## Spark Platform",
          "You are running under the Spark Harness (OpenCode engine).",
          "Prefer Spark tools for architecture, semantic twin, simulation, and knowledge:",
          "semantic_search, semantic_explain, semantic_trace_execution, semantic_trace_dependency,",
          "semantic_find_concept, architecture_review, simulation_run, knowledge_search.",
          "File edits automatically update the Semantic Twin — do not ask the user to sync.",
        ].join("\n"),
      )
    },

    tool: {
      semantic_search: tool("semantic.search", "Search the Spark Semantic Twin knowledge graph"),
      semantic_explain: tool("semantic.explain", "Explain a twin node (args: node_id, mode?)"),
      semantic_trace_execution: tool(
        "semantic.trace_execution",
        "Trace runtime/call execution path (args: node_id)",
      ),
      semantic_trace_dependency: tool(
        "semantic.trace_dependency",
        "Trace dependencies (args: node_id, direction?)",
      ),
      semantic_find_concept: tool("semantic.find_concept", "Find concepts in the twin (args: q)"),
      architecture_review: tool("architecture.review", "Run Spark architecture review on the twin"),
      simulation_run: tool(
        "simulation.run",
        "Simulate a change without modifying source (args: proposal)",
      ),
      knowledge_search: tool("knowledge.search", "Search org knowledge memory (args: q)"),
      runtime_select_model: tool(
        "runtime.select_model",
        "Request model selection via Spark Runtime (args: model)",
      ),
    },
  }
}

export default SparkPlugin
