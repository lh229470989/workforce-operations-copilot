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

export type ConversationItem = {
  id: string;
  actorId: number;
  prompt: string;
  response?: ChatResponse;
  error?: string;
};
