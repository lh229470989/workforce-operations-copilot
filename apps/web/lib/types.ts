export type Persona = {
  id: number;
  name: string;
  role: "employee" | "manager" | "admin";
  scope: string;
  initials: string;
};

export type ToolEvent = {
  id: string;
  name: string;
  status: "completed" | "failed";
  input: Record<string, unknown>;
  output: unknown;
};

export type Confirmation = {
  action: string;
  preview: Record<string, unknown>;
  confirmation_token: string;
  expires_at: string;
  confirm_path: string;
};

export type PolicyCitation = {
  source_id: string;
  title: string;
  section: string;
  path: string;
  excerpt: string;
};

export type ChartData = {
  type: "bar";
  title: string;
  x_key: string;
  series_key: string;
  value_key: string;
  rows: Array<Record<string, string>>;
};

export type TimeEntrySuggestion = {
  project_id: number;
  project_name: string;
  target_date: string;
  suggested_hours: string;
  suggested_description: string;
  based_on_entry_id: number;
  based_on_date: string;
};

export type TimeEntrySuggestionData = {
  type: "time_entry_suggestions";
  suggestions: TimeEntrySuggestion[];
};

export type WeeklyReportData = {
  type: "weekly_report";
  week_start: string;
  week_end: string;
  total_hours: string;
  entry_count: number;
  hours_by_status: Record<string, string>;
  entries: Array<Record<string, unknown>>;
};

export type ComparisonData = {
  type: "comparison";
  baseline: string;
  rows: Array<{
    label: string;
    project_name: string | null;
    start_date: string | null;
    end_date: string | null;
    status: string | null;
    entry_count: number;
    hours: string;
    delta_from_first: string;
  }>;
};

export type SafeAnalyticsData = {
  type: "safe_sql_analysis";
  dimension: string;
  metric: string;
  row_count: number;
  query_spec: Record<string, unknown>;
  rows: Array<{ dimension: string; value: string }>;
};

export type ChatResponse = {
  message: string;
  mode: "local" | "openai";
  session_id?: string;
  context?: {
    turn_count: number;
    actor_role: string;
    department_names: string[];
    recent_project_names: string[];
  };
  tool_events: ToolEvent[];
  citations?: PolicyCitation[];
  data: unknown;
  confirmation: Confirmation | null;
};

export type AgentProgressEvent = {
  kind: "status" | "tool";
  stage?: "planning" | "executing" | "composing";
  message?: string;
  intent?: string;
  name?: string;
  status?: "completed" | "failed";
};

export type ConversationItem = {
  id: string;
  actorId: number;
  prompt: string;
  response?: ChatResponse;
  progress?: AgentProgressEvent[];
  error?: string;
};
