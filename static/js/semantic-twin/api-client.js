/** Semantic Twin REST client */

const BASE = '/api/semantic-twin';

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) { /* ignore */ }
    throw new Error(`Twin API ${res.status}: ${detail}`);
  }
  return res.json();
}

export const TwinApiClient = {
  list: () => req('/'),
  get: (twinId, includeGraph = false) =>
    req(`/${encodeURIComponent(twinId)}${includeGraph ? '?include=graph' : ''}`),
  graph: (twinId) => req(`/${encodeURIComponent(twinId)}/graph`),
  generate: (body) => req('/generate', { method: 'POST', body: JSON.stringify(body) }),
  update: (twinId, body) =>
    req(`/${encodeURIComponent(twinId)}/update`, { method: 'POST', body: JSON.stringify(body) }),
  remove: (twinId) =>
    req(`/${encodeURIComponent(twinId)}`, { method: 'DELETE' }),
  search: (twinId, body) =>
    req(`/${encodeURIComponent(twinId)}/search`, { method: 'POST', body: JSON.stringify(body) }),
  explain: (twinId, body) =>
    req(`/${encodeURIComponent(twinId)}/explain`, { method: 'POST', body: JSON.stringify(body) }),
  traceExecution: (twinId, body) =>
    req(`/${encodeURIComponent(twinId)}/trace/execution`, { method: 'POST', body: JSON.stringify(body) }),
  traceDependency: (twinId, body) =>
    req(`/${encodeURIComponent(twinId)}/trace/dependency`, { method: 'POST', body: JSON.stringify(body) }),
  findConcept: (twinId, body) =>
    req(`/${encodeURIComponent(twinId)}/concepts`, { method: 'POST', body: JSON.stringify(body) }),
  quiz: (twinId, body = {}) =>
    req(`/${encodeURIComponent(twinId)}/quiz`, { method: 'POST', body: JSON.stringify(body) }),
  tutorial: (twinId, body = {}) =>
    req(`/${encodeURIComponent(twinId)}/tutorial`, { method: 'POST', body: JSON.stringify(body) }),
  simulate: (twinId, body) =>
    req(`/${encodeURIComponent(twinId)}/simulate`, { method: 'POST', body: JSON.stringify(body) }),
  compare: (twinId, body) =>
    req(`/${encodeURIComponent(twinId)}/compare`, { method: 'POST', body: JSON.stringify(body) }),
  node: (twinId, nodeId) =>
    req(`/${encodeURIComponent(twinId)}/node/${encodeURIComponent(nodeId)}`),
  story: (twinId, nodeId) =>
    req(`/${encodeURIComponent(twinId)}/story/${encodeURIComponent(nodeId)}`),
  // Phase 1
  listProjects: () => req('/projects/list'),
  getProject: (projectId) => req(`/projects/${encodeURIComponent(projectId)}`),
  registerProject: (body) =>
    req('/projects/register', { method: 'POST', body: JSON.stringify(body) }),
  timeline: (twinId) => req(`/${encodeURIComponent(twinId)}/timeline`),
  timelineVersion: (twinId, rev) =>
    req(`/${encodeURIComponent(twinId)}/timeline/${rev}`),
  timelineDiff: (twinId, fromRev, toRev) =>
    req(`/${encodeURIComponent(twinId)}/timeline/diff/${fromRev}/${toRev}`),
  runtimeEvent: (twinId, body) =>
    req(`/${encodeURIComponent(twinId)}/runtime`, { method: 'POST', body: JSON.stringify(body) }),
  runtimeEvents: (twinId, limit = 100) =>
    req(`/${encodeURIComponent(twinId)}/runtime?limit=${limit}`),
};

export default TwinApiClient;
