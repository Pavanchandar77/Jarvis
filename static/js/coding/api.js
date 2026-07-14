/** Coding Mode API — Workspace Manager (engine-agnostic) */

async function req(path, options = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let d = res.statusText;
    try { d = (await res.json()).detail || d; } catch (_) {}
    throw new Error(d);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const CodingAPI = {
  listWorkspaces: () => req('/api/workspaces/'),
  createWorkspace: (body) => req('/api/workspaces/', { method: 'POST', body: JSON.stringify(body) }),
  getWorkspace: (id) => req(`/api/workspaces/${encodeURIComponent(id)}`),
  status: (id) => req(`/api/workspaces/${encodeURIComponent(id)}/status`),
  ensureTwin: (id) => req(`/api/workspaces/${encodeURIComponent(id)}/twin/ensure`, { method: 'POST', body: '{}' }),
  startHarness: (id, body = {}) =>
    req(`/api/workspaces/${encodeURIComponent(id)}/harness/start`, { method: 'POST', body: JSON.stringify(body) }),
  listFiles: (id, path = '') =>
    req(`/api/workspaces/${encodeURIComponent(id)}/files?path=${encodeURIComponent(path)}`),
  readFile: (id, path) =>
    req(`/api/workspaces/${encodeURIComponent(id)}/file?path=${encodeURIComponent(path)}`),
  writeFile: (id, path, content) =>
    req(`/api/workspaces/${encodeURIComponent(id)}/file`, {
      method: 'PUT',
      body: JSON.stringify({ path, content }),
    }),
  filesChanged: (id, paths) =>
    req(`/api/workspaces/${encodeURIComponent(id)}/files-changed`, {
      method: 'POST',
      body: JSON.stringify({ workspace_id: id, paths }),
    }),
  // Twin
  twinSearch: (twinId, q) =>
    req(`/api/semantic-twin/${encodeURIComponent(twinId)}/search`, {
      method: 'POST',
      body: JSON.stringify({ q, limit: 20 }),
    }),
  twinExplain: (twinId, nodeId, mode = 'intermediate') =>
    req(`/api/semantic-twin/${encodeURIComponent(twinId)}/explain`, {
      method: 'POST',
      body: JSON.stringify({ node_id: nodeId, mode }),
    }),
  twinStory: (twinId, nodeId) =>
    req(`/api/semantic-twin/${encodeURIComponent(twinId)}/story/${encodeURIComponent(nodeId)}`),
  twinQuiz: (twinId) =>
    req(`/api/semantic-twin/${encodeURIComponent(twinId)}/quiz`, { method: 'POST', body: '{}' }),
  twinTutorial: (twinId, nodeId) =>
    req(`/api/semantic-twin/${encodeURIComponent(twinId)}/tutorial`, {
      method: 'POST',
      body: JSON.stringify({ focus_node_id: nodeId, max_steps: 8 }),
    }),
  twinSimulate: (twinId, proposal, nodeId) =>
    req(`/api/semantic-twin/${encodeURIComponent(twinId)}/simulate`, {
      method: 'POST',
      body: JSON.stringify({ proposal, focus_node_id: nodeId }),
    }),
  twinGraph: (twinId) => req(`/api/semantic-twin/${encodeURIComponent(twinId)}/graph`),
  // OS
  runtimeViz: (twinId) => req(`/api/os/runtime/${encodeURIComponent(twinId)}/visualization`),
  review: (twinId) => req(`/api/os/review/${encodeURIComponent(twinId)}`, { method: 'POST', body: '{}' }),
  memorySearch: (q) => req(`/api/os/memory/search?q=${encodeURIComponent(q || '')}`),
  agentBootstrap: (twinId) =>
    req(`/api/os/agents/${encodeURIComponent(twinId)}/bootstrap`, { method: 'POST', body: '{}' }),
  harnessEngines: () => req('/api/harness/engines'),
};

export default CodingAPI;
