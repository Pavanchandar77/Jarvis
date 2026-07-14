/** Living Workspace API — Twin is source of truth */

async function req(path, options = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let d = res.statusText;
    try { d = (await res.json()).detail || d; } catch (_) {}
    throw new Error(typeof d === 'string' ? d : JSON.stringify(d));
  }
  return res.json();
}

export const LivingAPI = {
  workspaces: () => req('/api/workspaces/'),
  workspace: (id) => req(`/api/workspaces/${encodeURIComponent(id)}`),
  workspaceStatus: (id) => req(`/api/workspaces/${encodeURIComponent(id)}/status`),
  ensureTwin: (id) => req(`/api/workspaces/${encodeURIComponent(id)}/twin/ensure`, { method: 'POST', body: '{}' }),
  listTwins: () => req('/api/semantic-twin/'),
  twin: (id) => req(`/api/semantic-twin/${encodeURIComponent(id)}?include=graph`),
  graph: (id) => req(`/api/semantic-twin/${encodeURIComponent(id)}/graph`),
  search: (id, q, kinds) =>
    req(`/api/semantic-twin/${encodeURIComponent(id)}/search`, {
      method: 'POST',
      body: JSON.stringify({ q, kinds, limit: 40 }),
    }),
  explain: (id, nodeId, mode = 'senior') =>
    req(`/api/semantic-twin/${encodeURIComponent(id)}/explain`, {
      method: 'POST',
      body: JSON.stringify({ node_id: nodeId, mode }),
    }),
  node: (id, nodeId) =>
    req(`/api/semantic-twin/${encodeURIComponent(id)}/node/${encodeURIComponent(nodeId)}`),
  story: (id, nodeId) =>
    req(`/api/semantic-twin/${encodeURIComponent(id)}/story/${encodeURIComponent(nodeId)}`),
  traceExec: (id, entryId) =>
    req(`/api/semantic-twin/${encodeURIComponent(id)}/trace/execution`, {
      method: 'POST',
      body: JSON.stringify({ entry_id: entryId, max_depth: 25 }),
    }),
  traceDep: (id, nodeId, direction = 'both') =>
    req(`/api/semantic-twin/${encodeURIComponent(id)}/trace/dependency`, {
      method: 'POST',
      body: JSON.stringify({ node_id: nodeId, direction, max_depth: 8 }),
    }),
  quiz: (id, nodeIds) =>
    req(`/api/semantic-twin/${encodeURIComponent(id)}/quiz`, {
      method: 'POST',
      body: JSON.stringify({ node_ids: nodeIds, count: 5 }),
    }),
  tutorial: (id, nodeId) =>
    req(`/api/semantic-twin/${encodeURIComponent(id)}/tutorial`, {
      method: 'POST',
      body: JSON.stringify({ focus_node_id: nodeId, max_steps: 10 }),
    }),
  simulate: (id, proposal, nodeId) =>
    req(`/api/semantic-twin/${encodeURIComponent(id)}/simulate`, {
      method: 'POST',
      body: JSON.stringify({ proposal, focus_node_id: nodeId }),
    }),
  timeline: (id) => req(`/api/os/timeline/${encodeURIComponent(id)}`),
  scrub: (id, rev, prior) =>
    req(`/api/os/timeline/${encodeURIComponent(id)}/scrub/${rev}${prior != null ? `?prior=${prior}` : ''}`),
  runtimeViz: (id) => req(`/api/os/runtime/${encodeURIComponent(id)}/visualization`),
  review: (id) => req(`/api/os/review/${encodeURIComponent(id)}`, { method: 'POST', body: '{}' }),
  memory: (q) => req(`/api/os/memory/search?q=${encodeURIComponent(q || '')}`),
  agents: (twinId) =>
    req(`/api/os/agents/${encodeURIComponent(twinId)}/bootstrap`, { method: 'POST', body: '{}' }),
  agentStatus: (projectId) => req(`/api/os/agents/${encodeURIComponent(projectId)}/status`),
  projects: () => req('/api/semantic-twin/projects/list'),
  engines: () => req('/api/harness/engines'),
  file: (wsId, path) =>
    req(`/api/workspaces/${encodeURIComponent(wsId)}/file?path=${encodeURIComponent(path)}`),
};

export default LivingAPI;
