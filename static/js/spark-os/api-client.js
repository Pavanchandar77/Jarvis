/** Spark OS REST client — Phase 2 capabilities */

const BASE = '/api/os';

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(`OS API ${res.status}: ${detail}`);
  }
  return res.json();
}

export const SparkOSClient = {
  status: () => req('/status'),
  // Architecture
  design: (body) => req('/architecture', { method: 'POST', body: JSON.stringify(body) }),
  listArchitectures: () => req('/architecture'),
  getArchitecture: (id) => req(`/architecture/${encodeURIComponent(id)}`),
  compile: (body) => req('/architecture/compile', { method: 'POST', body: JSON.stringify(body) }),
  // Requirements
  listRequirements: (twinId) => req(`/requirements/${encodeURIComponent(twinId)}`),
  linkRequirement: (twinId, body) =>
    req(`/requirements/${encodeURIComponent(twinId)}`, { method: 'POST', body: JSON.stringify(body) }),
  traceRequirement: (twinId, reqId) =>
    req(`/requirements/${encodeURIComponent(twinId)}/trace/${encodeURIComponent(reqId)}`),
  // Review
  review: (twinId) => req(`/review/${encodeURIComponent(twinId)}`, { method: 'POST', body: '{}' }),
  // Agents
  agentBootstrap: (twinId) =>
    req(`/agents/${encodeURIComponent(twinId)}/bootstrap`, { method: 'POST', body: '{}' }),
  agentStatus: (projectId) => req(`/agents/${encodeURIComponent(projectId)}/status`),
  agentMessage: (projectId, body) =>
    req(`/agents/${encodeURIComponent(projectId)}/message`, { method: 'POST', body: JSON.stringify(body) }),
  // Timeline
  timeline: (twinId, projectId) =>
    req(`/timeline/${encodeURIComponent(twinId)}${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`),
  scrub: (twinId, rev, prior) =>
    req(`/timeline/${encodeURIComponent(twinId)}/scrub/${rev}${prior != null ? `?prior=${prior}` : ''}`),
  // Simulation
  simulate: (twinId, body) =>
    req(`/simulate/${encodeURIComponent(twinId)}`, { method: 'POST', body: JSON.stringify(body) }),
  // Memory
  memorySearch: (q) => req(`/memory/search?q=${encodeURIComponent(q || '')}`),
  memoryLearn: (twinId) =>
    req(`/memory/learn/${encodeURIComponent(twinId)}`, { method: 'POST', body: '{}' }),
  // Runtime
  runtimeViz: (twinId) => req(`/runtime/${encodeURIComponent(twinId)}/visualization`),
  // Marketplace
  marketplace: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return req(`/marketplace${qs ? `?${qs}` : ''}`);
  },
  marketplaceGet: (slug) => req(`/marketplace/${encodeURIComponent(slug)}`),
  marketplaceUse: (slug, name) =>
    req(`/marketplace/${encodeURIComponent(slug)}/use${name ? `?name=${encodeURIComponent(name)}` : ''}`, {
      method: 'POST',
      body: '{}',
    }),
  // Refactor
  refactorCatalog: () => req('/refactor/catalog'),
  refactor: (twinId, body) =>
    req(`/refactor/${encodeURIComponent(twinId)}`, { method: 'POST', body: JSON.stringify(body) }),
};

export default SparkOSClient;
