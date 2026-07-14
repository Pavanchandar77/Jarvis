/** Viewing mode metadata for Semantic Twin explorer */

export const VIEWING_MODES = [
  { id: 'beginner', label: 'Beginner', hint: 'Plain language, no jargon' },
  { id: 'intermediate', label: 'Intermediate', hint: 'Assumptions & implementation' },
  { id: 'senior', label: 'Senior', hint: 'Architecture & trade-offs' },
  { id: 'runtime', label: 'Runtime', hint: 'Execution animation path' },
  { id: 'ai_reasoning', label: 'AI Reasoning', hint: 'Why the model chose this' },
  { id: 'performance', label: 'Performance', hint: 'Complexity & bottlenecks' },
  { id: 'security', label: 'Security', hint: 'Attack surface & mitigations' },
];

export const STORY_STAGES = [
  { id: 'prompt', label: 'Prompt', color: '#f59e0b' },
  { id: 'requirement', label: 'Requirement', color: '#3b82f6' },
  { id: 'design_decision', label: 'Design decision', color: '#eab308' },
  { id: 'generated_code', label: 'Generated code', color: '#22c55e' },
  { id: 'runtime_execution', label: 'Runtime execution', color: '#a855f7' },
  { id: 'dependencies', label: 'Dependencies', color: '#06b6d4' },
  { id: 'related_concepts', label: 'Related concepts', color: '#f472b6' },
];

export const KIND_COLORS = {
  application: '#94a3b8',
  module: '#64748b',
  component: '#22c55e',
  function: '#3b82f6',
  class: '#6366f1',
  method: '#60a5fa',
  hook: '#14b8a6',
  api_endpoint: '#f97316',
  route: '#fb923c',
  state_atom: '#eab308',
  concept: '#f472b6',
  prompt: '#f59e0b',
  requirement: '#38bdf8',
  design_decision: '#eab308',
  alternative: '#a3a3a3',
  security_surface: '#ef4444',
  test: '#84cc16',
};
