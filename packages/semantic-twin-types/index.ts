/**
 * Spark Semantic Twin — shared TypeScript contracts.
 * Python mirrors: services/semantic_twin/models.py
 * Schema version: 1.0.0
 */

export const SEMANTIC_TWIN_SCHEMA_VERSION = "1.0.0" as const;

export type NodeKind =
  | "application" | "module" | "package"
  | "component" | "function" | "class" | "method" | "hook"
  | "api_endpoint" | "api_client" | "middleware"
  | "state_store" | "state_atom" | "state_selector"
  | "route" | "page" | "layout"
  | "table" | "column" | "relation" | "migration"
  | "event" | "event_handler" | "subscription"
  | "data_flow" | "transform"
  | "prompt" | "requirement" | "design_decision" | "alternative"
  | "concept" | "pattern" | "resource"
  | "test" | "coverage_gap"
  | "security_surface" | "perf_hotspot" | "error";

export type EdgeKind =
  | "contains" | "depends_on" | "imports" | "calls" | "renders"
  | "reads_state" | "writes_state" | "routes_to" | "data_flows_to" | "fk_to"
  | "emits" | "handles" | "generated_from" | "decided_by" | "alternative_to"
  | "related_to" | "illustrates";

export type ViewingMode =
  | "beginner" | "intermediate" | "senior" | "runtime"
  | "ai_reasoning" | "performance" | "security";

export type CreatedBy = "ai" | "human" | `plugin:${string}`;

export interface SourceLocation {
  start_line: number;
  end_line: number;
  start_col?: number;
  end_col?: number;
}

export interface LearningResource {
  title: string;
  url?: string;
  kind: "docs" | "article" | "video" | "internal" | "concept";
  difficulty?: number;
}

export interface SuggestedImprovement {
  summary: string;
  rationale: string;
  impact: "low" | "medium" | "high";
  effort: "low" | "medium" | "high";
  category: "performance" | "security" | "maintainability" | "a11y" | "testing" | "dx";
}

export interface ViewContent {
  mode: ViewingMode;
  title: string;
  body: string;
  bullets?: string[];
  code_refs?: string[];
  warnings?: string[];
  metrics?: Record<string, string | number>;
}

export interface SemanticNode {
  id: string;
  kind: NodeKind;
  name: string;
  description: string;
  purpose: string;
  why_exists: string;
  created_by: CreatedBy;
  prompt_id: string | null;
  dependencies: string[];
  dependents: string[];
  source_file: string | null;
  source_location: SourceLocation | null;
  execution_order: number | null;
  related_concepts: string[];
  suggested_improvements: SuggestedImprovement[];
  learning_resources: LearningResource[];
  difficulty_score: number;
  views: Partial<Record<ViewingMode, ViewContent>>;
  attributes: Record<string, unknown>;
}

export interface SemanticEdge {
  id: string;
  kind: EdgeKind;
  source: string;
  target: string;
  weight: number;
  attributes: Record<string, unknown>;
}

export interface AlternativeImplementation {
  id: string;
  title: string;
  summary: string;
  why_rejected: string;
  when_preferable?: string;
}

export interface DesignDecision {
  id: string;
  title: string;
  rationale: string;
  chosen: string;
  alternatives: AlternativeImplementation[];
  prompt_id: string | null;
  related_node_ids: string[];
  trade_offs: string[];
}

export interface PromptRecord {
  id: string;
  ordinal: number;
  role: "system" | "user" | "tool" | "assistant";
  text_ref: string;
  model?: string;
  created_at?: string;
}

export interface GenerationManifest {
  generation_id: string;
  model_ids: string[];
  prompts: PromptRecord[];
  requirements: Array<{ id: string; text: string; prompt_id?: string }>;
  decisions: DesignDecision[];
  file_prompt_map: Record<string, string[]>;
  tech_stack: string[];
  created_at: string;
  metadata: Record<string, unknown>;
  /** Phase 1 — AI intent preservation */
  user_prompt?: string;
  planning_prompt?: string;
  agent_chain?: Array<Record<string, unknown>>;
  tool_history?: Array<Record<string, unknown>>;
  backend?: string;
  runtime_metadata?: Record<string, unknown>;
  file_ownership?: Record<string, string>;
  component_ownership?: Record<string, string>;
  dependency_reasoning?: Array<Record<string, unknown>>;
  trade_offs?: string[];
}

export interface TwinMeta {
  application_id: string;
  application_name: string;
  entrypoints: string[];
  tech_stack: string[];
  node_count: number;
  edge_count: number;
  languages: string[];
  coverage_summary?: {
    tests: number;
    gaps: number;
    estimated_ratio?: number;
  };
}

export interface TwinIndexes {
  by_file: Record<string, string[]>;
  by_kind: Record<string, string[]>;
  by_name: Record<string, string[]>;
  adjacency_out: Record<string, string[]>;
  adjacency_in: Record<string, string[]>;
  concepts: Record<string, string>;
}

export interface SemanticTwin {
  twin_id: string;
  application_id: string;
  schema_version: string;
  content_revision: number;
  content_hash: string;
  created_at: string;
  updated_at: string;
  owner: string | null;
  manifest: GenerationManifest;
  nodes: SemanticNode[];
  edges: SemanticEdge[];
  indexes: TwinIndexes;
  meta: TwinMeta;
}

export interface SearchQuery {
  q: string;
  kinds?: NodeKind[];
  limit?: number;
  mode?: ViewingMode;
}

export interface SearchHit {
  node_id: string;
  name: string;
  kind: NodeKind;
  score: number;
  snippet: string;
}

export interface SearchResult {
  hits: SearchHit[];
  total: number;
}

export interface ExplainRequest {
  node_id: string;
  mode: ViewingMode;
}

export interface ExplainResult {
  node_id: string;
  mode: ViewingMode;
  content: ViewContent;
  related: Array<{ id: string; name: string; kind: NodeKind }>;
}

export interface TraceStep {
  node_id: string;
  name: string;
  kind: NodeKind;
  order: number;
  note?: string;
}

export interface TraceExecutionResult {
  entry_id: string;
  steps: TraceStep[];
  edges: string[];
}

export interface TraceDependencyResult {
  root_id: string;
  direction: "upstream" | "downstream" | "both";
  nodes: string[];
  edges: string[];
  depth: number;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  choices: string[];
  correct_index: number;
  explanation: string;
  node_ids: string[];
  difficulty: number;
}

export interface Quiz {
  id: string;
  title: string;
  questions: QuizQuestion[];
}

export interface TutorialStep {
  id: string;
  title: string;
  body: string;
  node_ids: string[];
  mode: ViewingMode;
}

export interface Tutorial {
  id: string;
  title: string;
  steps: TutorialStep[];
}

export interface SimulationResult {
  proposal: string;
  affected_node_ids: string[];
  risk_level: "low" | "medium" | "high";
  predicted_breaks: string[];
  suggested_tests: string[];
  narrative: string;
}

export interface VersionDiff {
  from_revision: number;
  to_revision: number;
  added_nodes: string[];
  removed_nodes: string[];
  modified_nodes: string[];
  added_edges: string[];
  removed_edges: string[];
  summary: string;
}

export interface TwinApi {
  search(query: SearchQuery): Promise<SearchResult>;
  explain(req: ExplainRequest): Promise<ExplainResult>;
  traceExecution(entryId: string, maxDepth?: number): Promise<TraceExecutionResult>;
  traceDependency(
    nodeId: string,
    direction?: "upstream" | "downstream" | "both",
    maxDepth?: number
  ): Promise<TraceDependencyResult>;
  findConcept(query: string, limit?: number): Promise<SearchResult>;
  generateQuiz(opts?: { node_ids?: string[]; difficulty?: number; count?: number }): Promise<Quiz>;
  generateTutorial(opts?: { focus_node_id?: string; max_steps?: number }): Promise<Tutorial>;
  simulateModification(proposal: string, focus_node_id?: string): Promise<SimulationResult>;
  compareVersions(fromRevision: number, toRevision?: number): Promise<VersionDiff>;
}

export type StoryStage =
  | "prompt" | "requirement" | "design_decision" | "generated_code"
  | "runtime_execution" | "dependencies" | "related_concepts";

export interface AnimStep {
  kind: StoryStage;
  node_ids: string[];
  edge_ids: string[];
  panel_mode: ViewingMode;
  duration_ms: number;
  label: string;
}
