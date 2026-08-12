"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { DEMO_PROMPTS, PERSONAS } from "@/lib/personas";
import type {
  AgentProgressEvent,
  ChartData,
  ChatResponse,
  ComparisonData,
  Confirmation,
  ConversationItem,
  PolicyCitation,
  ReportExportData,
  SafeAnalyticsData,
  TimeEntryRow,
  TimeEntrySuggestionData,
  ToolEvent,
  WeeklyReportData,
} from "@/lib/types";

function AgentProgress({ events }: { events: AgentProgressEvent[] }) {
  return (
    <section className="agent-progress" aria-label="Agent progress">
      <span className="section-label">LIVE AGENT STATUS</span>
      {events.map((event, index) => (
        <div className="progress-row" key={`${event.kind}-${event.stage ?? event.name}-${index}`}>
          <span className={`progress-dot ${event.status ?? "active"}`} />
          <strong>
            {event.kind === "tool"
              ? event.name?.replaceAll("_", " ")
              : event.message}
          </strong>
          <small>{event.intent ?? event.status ?? event.stage}</small>
        </div>
      ))}
    </section>
  );
}

function isChartData(data: unknown): data is ChartData {
  return (
    typeof data === "object" &&
    data !== null &&
    "type" in data &&
    data.type === "bar" &&
    "rows" in data &&
    Array.isArray(data.rows)
  );
}

function isSuggestionData(data: unknown): data is TimeEntrySuggestionData {
  return (
    typeof data === "object" &&
    data !== null &&
    "type" in data &&
    data.type === "time_entry_suggestions" &&
    "suggestions" in data &&
    Array.isArray(data.suggestions)
  );
}

function isTimeEntryRows(data: unknown): data is TimeEntryRow[] {
  return Array.isArray(data) && data.every((row) => (
    typeof row === "object" && row !== null &&
    "work_date" in row && "hours" in row && "status" in row &&
    "project_name" in row
  ));
}

function TimeEntryTable({ rows }: { rows: TimeEntryRow[] }) {
  return (
    <section className="comparison-table" aria-label="Time entries">
      <span className="section-label">ROLE-SCOPED TIME ENTRIES · {rows.length}</span>
      {rows.length === 0 ? <p>No matching time entries.</p> : (
        <table>
          <thead><tr><th>Date</th><th>Project</th><th>Hours</th><th>Status</th><th>Description</th></tr></thead>
          <tbody>{rows.map((row) => (
            <tr key={row.id}>
              <td>{row.work_date}</td><td>{row.project_name}</td><td>{row.hours}</td>
              <td><span className={`entry-status ${row.status}`}>{row.status}</span></td>
              <td>{row.description}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </section>
  );
}

function isWeeklyReportData(data: unknown): data is WeeklyReportData {
  return (
    typeof data === "object" &&
    data !== null &&
    "type" in data &&
    data.type === "weekly_report"
  );
}

function isReportExportData(data: unknown): data is ReportExportData {
  return (
    typeof data === "object" && data !== null && "type" in data &&
    data.type === "report_export" && "filters" in data
  );
}

function isComparisonData(data: unknown): data is ComparisonData {
  return (
    typeof data === "object" &&
    data !== null &&
    "type" in data &&
    data.type === "comparison" &&
    "rows" in data &&
    Array.isArray(data.rows)
  );
}

function isSafeAnalyticsData(data: unknown): data is SafeAnalyticsData {
  return (
    typeof data === "object" && data !== null && "type" in data &&
    data.type === "safe_sql_analysis" && "rows" in data && Array.isArray(data.rows)
  );
}

function SafeAnalyticsTable({ data }: { data: SafeAnalyticsData }) {
  return (
    <section className="comparison-table" aria-label="Safe analytics result">
      <span className="section-label">SAFE READ MODEL · NO RAW SQL</span>
      <table><thead><tr><th>{data.dimension}</th><th>{data.metric}</th></tr></thead>
        <tbody>{data.rows.map((row) => <tr key={row.dimension}><td>{row.dimension}</td><td>{row.value}</td></tr>)}</tbody>
      </table>
      <details><summary>Validated query specification</summary><pre className="preview-json">{JSON.stringify(data.query_spec, null, 2)}</pre></details>
    </section>
  );
}

function ComparisonTable({ data }: { data: ComparisonData }) {
  return (
    <section className="comparison-table" aria-label="Comparison analysis">
      <span className="section-label">BASELINE · {data.baseline}</span>
      <table>
        <thead><tr><th>Slice</th><th>Range</th><th>Entries</th><th>Hours</th><th>Δ</th></tr></thead>
        <tbody>
          {data.rows.map((row) => (
            <tr key={row.label}>
              <td><strong>{row.label}</strong><small>{row.project_name}</small></td>
              <td>{row.start_date ? `${row.start_date} → ${row.end_date}` : "All visible dates"}</td>
              <td>{row.entry_count}</td><td>{row.hours}</td><td>{row.delta_from_first}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function WeeklyReport({ data, actorId }: { data: WeeklyReportData; actorId: number }) {
  const download = `/api/reports/weekly.csv?actorId=${actorId}&week_start=${encodeURIComponent(data.week_start)}`;
  return (
    <section className="weekly-report" aria-label="Weekly report">
      <div>
        <span className="eyebrow">WEEKLY REPORT</span>
        <strong>{data.week_start} → {data.week_end}</strong>
      </div>
      <div><b>{data.total_hours}</b><span>hours</span></div>
      <div><b>{data.entry_count}</b><span>entries</span></div>
      <a href={download}>Download role-scoped CSV</a>
    </section>
  );
}

function ReportExport({ data, actorId }: { data: ReportExportData; actorId: number }) {
  const params = new URLSearchParams({ actorId: String(actorId) });
  Object.entries(data.filters).forEach(([key, value]) => params.set(key, String(value)));
  return (
    <section className="weekly-report" aria-label="Report export">
      <div><span className="eyebrow">ROLE-SCOPED EXPORT</span><strong>Time-entry CSV</strong></div>
      <div><b>{data.row_count}</b><span>matching rows</span></div>
      <a href={`/api/reports/time-entries.csv?${params}`}>Download CSV</a>
    </section>
  );
}

function ToolCard({ event }: { event: ToolEvent }) {
  return (
    <details className="tool-card">
      <summary>
        <span className="tool-status" aria-hidden="true">
          ✓
        </span>
        <span>{event.name.replaceAll("_", " ")}</span>
        <span className="tool-label">tool call</span>
      </summary>
      <div className="tool-detail">
        <div>
          <span>INPUT</span>
          <pre>{JSON.stringify(event.input, null, 2)}</pre>
        </div>
        <div>
          <span>OUTPUT</span>
          <pre>{JSON.stringify(event.output, null, 2)}</pre>
        </div>
      </div>
    </details>
  );
}

function HoursChart({ chart }: { chart: ChartData }) {
  const maximum = Math.max(
    ...chart.rows.map((row) => Number(row[chart.value_key] ?? 0)),
    1,
  );

  return (
    <section className="chart-card" aria-label={chart.title}>
      <div className="chart-heading">
        <div>
          <span className="eyebrow">ROLE-SCOPED ANALYTICS</span>
          <h3>{chart.title}</h3>
        </div>
        <span className="chart-unit">hours</span>
      </div>
      <div className="bars">
        {chart.rows.map((row, index) => {
          const value = Number(row[chart.value_key] ?? 0);
          const label = `${row[chart.x_key]} · ${row[chart.series_key]}`;
          return (
            <div className="bar-row" key={`${label}-${index}`}>
              <div className="bar-meta">
                <span>{label}</span>
                <strong>{value.toFixed(2)}</strong>
              </div>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${Math.max((value / maximum) * 100, 3)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function CitationList({ citations }: { citations: PolicyCitation[] }) {
  return (
    <section className="citations" aria-label="Policy sources">
      <span className="section-label">GROUNDED POLICY SOURCES</span>
      {citations.map((citation) => (
        <article
          className="citation-card"
          key={`${citation.source_id}-${citation.section}`}
        >
          <div>
            <strong>{citation.title}</strong>
            <span>{citation.section}</span>
          </div>
          <p>{citation.excerpt}</p>
          <code>{citation.path}</code>
        </article>
      ))}
    </section>
  );
}

function SuggestionList({ data }: { data: TimeEntrySuggestionData }) {
  return (
    <section className="suggestion-list" aria-label="Time entry suggestions">
      <div className="suggestion-heading">
        <span className="section-label">RECENT-WORK SUGGESTIONS</span>
        <span className="suggestion-badge">REVIEW BEFORE DRAFTING</span>
      </div>
      {data.suggestions.length === 0 ? (
        <p>No personal recent work is available for suggestions.</p>
      ) : (
        data.suggestions.map((suggestion) => (
          <article className="suggestion-card" key={suggestion.project_id}>
            <div>
              <strong>{suggestion.project_name}</strong>
              <span>{suggestion.target_date}</span>
            </div>
            <p>{suggestion.suggested_description}</p>
            <small>
              {suggestion.suggested_hours} hours · based on your entry from{" "}
              {suggestion.based_on_date}
            </small>
          </article>
        ))
      )}
    </section>
  );
}

function PreviewValue({ value }: { value: unknown }) {
  if (typeof value === "object" && value !== null) {
    return <pre className="preview-json">{JSON.stringify(value, null, 2)}</pre>;
  }
  return <span>{value === null || value === undefined ? "—" : String(value)}</span>;
}

function ConfirmationCard({
  confirmation,
  actorId,
  onResolved,
}: {
  confirmation: Confirmation;
  actorId: number;
  onResolved: (message: string) => void;
}) {
  const [state, setState] = useState<"idle" | "working" | "done" | "cancelled">(
    "idle",
  );
  const [error, setError] = useState("");

  async function confirm() {
    setState("working");
    setError("");
    const response = await fetch(
      `/api/actions/${confirmation.confirmation_token}/confirm`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actorId, confirm: true }),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      setState("idle");
      setError(payload.detail ?? "Confirmation failed.");
      return;
    }
    setState("done");
    const count = Number(payload?.result?.count ?? 1);
    const decidedStatus = payload?.result?.time_entry?.status;
    onResolved(
      confirmation.action === "create_time_entries"
        ? `Confirmed. ${count} time entries were created atomically and audited.`
        : confirmation.action === "decide_time_entry"
          ? `Confirmed. The time entry was ${decidedStatus ?? "decided"} and the approval was audited.`
          : "Confirmed. The time entry was created and audited.",
    );
  }

  if (state === "cancelled") {
    return <div className="resolution-note">Proposal dismissed. No write was made.</div>;
  }

  return (
    <section className="confirmation-card" aria-label="Confirmation required">
      <div className="confirmation-head">
        <div className="shield">✓</div>
        <div>
          <span className="eyebrow">EXPLICIT CONFIRMATION REQUIRED</span>
          <h3>
            {confirmation.action === "create_time_entries"
              ? "Review batch time entry draft"
              : confirmation.action === "decide_time_entry"
                ? "Review approval decision"
                : confirmation.action === "decide_time_entries"
                  ? "Review batch approval decision"
                : confirmation.action === "update_time_entry"
                  ? "Review time entry changes"
                  : confirmation.action === "delete_time_entry"
                    ? "Review time entry deletion"
                    : confirmation.action === "transition_time_entry"
                      ? "Review status transition"
                : "Review time entry draft"}
          </h3>
        </div>
        <span className="dry-run-badge">DRY RUN</span>
      </div>
      <div className="preview-grid">
        {Object.entries(confirmation.preview).map(([key, value]) => (
          <div key={key}>
            <span>{key.replaceAll("_", " ")}</span>
            <PreviewValue value={value} />
          </div>
        ))}
      </div>
      <p className="expiry">
        Token expires {new Date(confirmation.expires_at).toLocaleString()}.
        Nothing changes until you confirm.
      </p>
      {error && <p className="inline-error">{error}</p>}
      <div className="confirmation-actions">
        <button
          className="secondary-button"
          disabled={state !== "idle"}
          onClick={() => setState("cancelled")}
          type="button"
        >
          Dismiss
        </button>
        <button
          className="confirm-button"
          disabled={state !== "idle"}
          onClick={confirm}
          type="button"
        >
          {state === "working"
            ? "Confirming…"
            : state === "done"
              ? "Confirmed"
              : confirmation.action === "decide_time_entry"
                ? "Confirm decision"
                : confirmation.action === "decide_time_entries"
                  ? "Confirm batch decision"
                : confirmation.action === "delete_time_entry"
                  ? "Confirm deletion"
                  : confirmation.action === "update_time_entry" || confirmation.action === "transition_time_entry"
                    ? "Confirm change"
                : "Confirm & create"}
        </button>
      </div>
    </section>
  );
}

function AssistantResponse({
  response,
  actorId,
}: {
  response: ChatResponse;
  actorId: number;
}) {
  const [resolution, setResolution] = useState("");
  return (
    <div className="assistant-block">
      <div className="assistant-mark">A</div>
      <div className="assistant-content">
        <div className="response-meta">
          <strong>Acme Copilot</strong>
          <span>
            {response.mode === "openai" ? "LLM agent" : "local fallback"}
            {response.context
              ? ` · ${response.context.turn_count} turn context`
              : ""}
          </span>
        </div>
        <p className="assistant-message">{response.message}</p>
        {isTimeEntryRows(response.data) && <TimeEntryTable rows={response.data} />}
        {response.citations && response.citations.length > 0 && (
          <CitationList citations={response.citations} />
        )}
        {isChartData(response.data) && <HoursChart chart={response.data} />}
        {isSuggestionData(response.data) && (
          <SuggestionList data={response.data} />
        )}
        {isWeeklyReportData(response.data) && (
          <WeeklyReport actorId={actorId} data={response.data} />
        )}
        {isReportExportData(response.data) && (
          <ReportExport actorId={actorId} data={response.data} />
        )}
        {isComparisonData(response.data) && <ComparisonTable data={response.data} />}
        {isSafeAnalyticsData(response.data) && <SafeAnalyticsTable data={response.data} />}
        {response.tool_events.length > 0 && (
          <div className="tools">
            <span className="section-label">
              {response.tool_events.length} TOOL EVENT
              {response.tool_events.length === 1 ? "" : "S"}
            </span>
            {response.tool_events.map((event) => (
              <ToolCard event={event} key={event.id} />
            ))}
          </div>
        )}
        {response.confirmation && (
          <ConfirmationCard
            actorId={actorId}
            confirmation={response.confirmation}
            onResolved={setResolution}
          />
        )}
        {resolution && <div className="resolution-note">{resolution}</div>}
      </div>
    </div>
  );
}

type PreferenceState = {
  actor_id: number;
  history_enabled: boolean;
  preferred_language: "auto" | "en" | "zh";
  preferred_project_id: number | null;
  response_detail: "concise" | "standard" | "detailed";
  report_format: "summary" | "csv";
};

type PreferencePreview = {
  action: string;
  preview: Record<string, unknown>;
  confirmation_token: string;
};

type StructuredMemory = {
  id: string;
  category: "work_preference" | "reporting_preference" | "collaboration_preference";
  value: string;
};

function PrivacyControls({ actorId }: { actorId: number }) {
  const [current, setCurrent] = useState<PreferenceState | null>(null);
  const [historyEnabled, setHistoryEnabled] = useState(true);
  const [language, setLanguage] = useState<"auto" | "en" | "zh">("auto");
  const [preferredProject, setPreferredProject] = useState("");
  const [responseDetail, setResponseDetail] = useState<"concise" | "standard" | "detailed">("standard");
  const [reportFormat, setReportFormat] = useState<"summary" | "csv">("summary");
  const [preview, setPreview] = useState<PreferencePreview | null>(null);
  const [memories, setMemories] = useState<StructuredMemory[]>([]);
  const [memoryCategory, setMemoryCategory] = useState<StructuredMemory["category"]>("work_preference");
  const [memoryValue, setMemoryValue] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    const [response, memoryResponse] = await Promise.all([
      fetch(`/api/preferences?actorId=${actorId}`, { cache: "no-store" }),
      fetch(`/api/memories?actorId=${actorId}`, { cache: "no-store" }),
    ]);
    const payload = (await response.json()) as PreferenceState;
    if (!response.ok) return;
    if (memoryResponse.ok) {
      const memoryPayload = await memoryResponse.json() as unknown;
      setMemories(Array.isArray(memoryPayload) ? memoryPayload as StructuredMemory[] : []);
    }
    setCurrent(payload); setHistoryEnabled(payload.history_enabled);
    setLanguage(payload.preferred_language);
    setPreferredProject(payload.preferred_project_id?.toString() ?? "");
    setResponseDetail(payload.response_detail);
    setReportFormat(payload.report_format);
    setPreview(null); setNotice("");
  }

  async function prepareUpdate() {
    const response = await fetch("/api/preferences", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actorId,
        history_enabled: historyEnabled,
        preferred_language: language,
        preferred_project_id: preferredProject ? Number(preferredProject) : undefined,
        clear_preferred_project: !preferredProject,
        response_detail: responseDetail,
        report_format: reportFormat,
      }),
    });
    if (response.ok) setPreview((await response.json()) as PreferencePreview);
  }

  async function prepareDeletion() {
    const response = await fetch("/api/preferences/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actorId }),
    });
    if (response.ok) setPreview((await response.json()) as PreferencePreview);
  }

  async function prepareMemory() {
    const response = await fetch("/api/memories", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actorId, category: memoryCategory, value: memoryValue }),
    });
    if (response.ok) setPreview((await response.json()) as PreferencePreview);
  }

  async function prepareMemoryDeletion(memoryId: string) {
    const response = await fetch(`/api/memories/${memoryId}?actorId=${actorId}`, { method: "DELETE" });
    if (response.ok) setPreview((await response.json()) as PreferencePreview);
  }

  async function confirm() {
    if (!preview) return;
    const isMemoryAction = preview.action.endsWith("_memory");
    const actionPath = isMemoryAction ? "memories" : "preferences";
    const response = await fetch(
      `/api/${actionPath}/actions/${preview.confirmation_token}/confirm`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ actorId, confirm: true }) },
    );
    if (response.ok) {
      const completedNotice = preview.action === "delete_private_state"
        ? "Private state deleted."
        : isMemoryAction ? "Structured memory updated." : "Preferences saved.";
      if (isMemoryAction) setMemoryValue("");
      setPreview(null); await load(); setNotice(completedNotice);
    }
  }

  return (
    <details className="privacy-controls">
      <summary>Privacy & memory</summary>
      {!current ? (
        <button type="button" onClick={() => void load()}>Load my settings</button>
      ) : (
        <>
          <label><input checked={historyEnabled} onChange={(event) => setHistoryEnabled(event.target.checked)} type="checkbox" /> Persist bounded chat history</label>
          <label>Reply preference<select value={language} onChange={(event) => setLanguage(event.target.value as "auto" | "en" | "zh")}><option value="auto">Match request</option><option value="en">English</option><option value="zh">中文</option></select></label>
          <label>Preferred visible project ID<input min="1" onChange={(event) => setPreferredProject(event.target.value)} placeholder="Optional" type="number" value={preferredProject} /></label>
          <label>Response detail<select value={responseDetail} onChange={(event) => setResponseDetail(event.target.value as "concise" | "standard" | "detailed")}><option value="concise">Concise</option><option value="standard">Standard</option><option value="detailed">Detailed</option></select></label>
          <label>Default report format<select value={reportFormat} onChange={(event) => setReportFormat(event.target.value as "summary" | "csv")}><option value="summary">On-screen summary</option><option value="csv">CSV download</option></select></label>
          <button type="button" onClick={() => void prepareUpdate()}>Preview changes</button>
          <div className="structured-memory-list">
            <strong>Explicit structured memories</strong>
            {memories.length === 0 && <small>No saved memory facts.</small>}
            {memories.map((memory) => <div key={memory.id}><span>{memory.category.replaceAll("_", " ")}: {memory.value}</span><button type="button" onClick={() => void prepareMemoryDeletion(memory.id)}>Preview delete</button></div>)}
          </div>
          <label>Memory category<select value={memoryCategory} onChange={(event) => setMemoryCategory(event.target.value as StructuredMemory["category"])}><option value="work_preference">Work preference</option><option value="reporting_preference">Reporting preference</option><option value="collaboration_preference">Collaboration preference</option></select></label>
          <label>Non-sensitive preference<input maxLength={200} value={memoryValue} onChange={(event) => setMemoryValue(event.target.value)} placeholder="Explicit facts only" /></label>
          <button disabled={!memoryValue.trim()} type="button" onClick={() => void prepareMemory()}>Preview memory</button>
          <button className="danger-link" type="button" onClick={() => void prepareDeletion()}>Preview private-state deletion</button>
        </>
      )}
      {preview && <div className="privacy-preview"><strong>DRY RUN · {preview.action.replaceAll("_", " ")}</strong><pre>{JSON.stringify(preview.preview, null, 2)}</pre><button type="button" onClick={() => void confirm()}>Explicitly confirm</button><button type="button" onClick={() => setPreview(null)}>Dismiss</button></div>}
      {notice && <p>{notice}</p>}
    </details>
  );
}

function ReportControls({ actorId }: { actorId: number }) {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [status, setStatus] = useState("");
  const [projectId, setProjectId] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const query = new URLSearchParams({ actorId: String(actorId) });
  if (startDate) query.set("start_date", startDate);
  if (endDate) query.set("end_date", endDate);
  if (status) query.set("status", status);
  if (projectId) query.set("project_id", projectId);
  if (employeeId) query.set("employee_id", employeeId);
  return (
    <details className="privacy-controls">
      <summary>Report export</summary>
      <label>From<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
      <label>To<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
      <label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All visible</option><option value="draft">Draft</option><option value="submitted">Submitted</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select></label>
      <label>Project ID<input min="1" type="number" value={projectId} onChange={(event) => setProjectId(event.target.value)} placeholder="Optional" /></label>
      <label>Employee ID<input min="1" type="number" value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} placeholder="Optional / scoped" /></label>
      <a className="secondary-button" href={`/api/reports/time-entries.csv?${query}`}>Download scoped CSV</a>
    </details>
  );
}

type AuditItem = { id: number; actor_id: number; action: string; resource_id: string; created_at: string };
type AgentAuditItem = { id: number; request_id: string; intent: string; tool_names: string[]; status: string; mode: string };

function AdminControls({ actorId }: { actorId: number }) {
  const [audit, setAudit] = useState<AuditItem[]>([]);
  const [agentAudit, setAgentAudit] = useState<AgentAuditItem[]>([]);
  const [notice, setNotice] = useState("");
  const [auditStats, setAuditStats] = useState<{ total: number; by_action: Record<string, number> } | null>(null);
  if (actorId !== 1) return null;

  async function loadAudit() {
    const [eventsResponse, statsResponse, agentResponse] = await Promise.all([
      fetch(`/api/admin/audit?actorId=${actorId}&page_size=8`, { cache: "no-store" }),
      fetch(`/api/admin/audit?actorId=${actorId}&stats=1`, { cache: "no-store" }),
      fetch(`/api/admin/agent-audit?actorId=${actorId}`, { cache: "no-store" }),
    ]);
    if (eventsResponse.ok) setAudit(((await eventsResponse.json()) as { items: AuditItem[] }).items);
    if (statsResponse.ok) setAuditStats(await statsResponse.json() as { total: number; by_action: Record<string, number> });
    if (agentResponse.ok) setAgentAudit((await agentResponse.json() as AgentAuditItem[]).slice(0, 8));
  }

  async function reloadKnowledge() {
    const response = await fetch(`/api/admin/knowledge?actorId=${actorId}`, { method: "POST" });
    const payload = await response.json() as { documents?: number; chunks?: number; detail?: string };
    setNotice(response.ok ? `Reloaded ${payload.documents} documents / ${payload.chunks} chunks.` : payload.detail ?? "Reload failed.");
  }

  return (
    <details className="privacy-controls">
      <summary>Admin operations</summary>
      <button type="button" onClick={() => void loadAudit()}>Load audit events</button>
      <button type="button" onClick={() => void reloadKnowledge()}>Reload knowledge base</button>
      {notice && <p>{notice}</p>}
      {auditStats && <p>{auditStats.total} confirmed write event(s) · {Object.keys(auditStats.by_action).length} action type(s)</p>}
      {audit.length > 0 && <ul>{audit.map((item) => <li key={item.id}><strong>{item.action}</strong> · actor {item.actor_id} · #{item.resource_id}</li>)}</ul>}
      {agentAudit.length > 0 && <><strong>Metadata-only agent executions</strong><ul>{agentAudit.map((item) => <li key={item.id}><strong>{item.intent}</strong> · {item.mode} · {item.status} · {item.tool_names.join(", ") || "no tools"}</li>)}</ul></>}
    </details>
  );
}

export function ChatWorkspace() {
  const [actorId, setActorId] = useState(3);
  const [input, setInput] = useState("");
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  const [busy, setBusy] = useState(false);
  const conversationEndRef = useRef<HTMLDivElement>(null);
  const sessionsRef = useRef<Record<number, string>>({});
  const persona = useMemo(
    () => PERSONAS.find((candidate) => candidate.id === actorId) ?? PERSONAS[0],
    [actorId],
  );

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView?.({
      behavior: "smooth",
      block: "end",
    });
  }, [conversation]);

  async function submit(message: string) {
    const trimmed = message.trim();
    if (!trimmed || busy) return;
    const id = crypto.randomUUID();
    const requestActor = actorId;
    setConversation((items) => [
      ...items,
      { id, actorId: requestActor, prompt: trimmed },
    ]);
    setInput("");
    setBusy(true);
    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actorId: requestActor,
          message: trimmed,
          sessionId: sessionsRef.current[requestActor],
        }),
      });
      const contentType = response.headers.get("content-type") ?? "";
      if (!response.ok || !contentType.includes("text/event-stream")) {
        const payload = (await response.json()) as ChatResponse & {
          detail?: string;
        };
        if (response.ok && payload.session_id) {
          sessionsRef.current[requestActor] = payload.session_id;
        }
        setConversation((items) =>
          items.map((item) =>
            item.id === id
              ? response.ok
                ? { ...item, response: payload }
                : { ...item, error: payload.detail ?? "Request failed." }
              : item,
          ),
        );
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Streaming response has no body");
      const decoder = new TextDecoder();
      let buffer = "";
      let finalPayload: ChatResponse | null = null;

      function consumeBlock(block: string) {
        const eventName = block
          .split("\n")
          .find((line) => line.startsWith("event: "))
          ?.slice(7);
        const data = block
          .split("\n")
          .filter((line) => line.startsWith("data: "))
          .map((line) => line.slice(6))
          .join("\n");
        if (!eventName || !data) return;
        const payload = JSON.parse(data) as Record<string, unknown>;
        if (eventName === "status" || eventName === "tool") {
          const progress = {
            kind: eventName,
            ...payload,
          } as AgentProgressEvent;
          setConversation((items) =>
            items.map((item) =>
              item.id === id
                ? { ...item, progress: [...(item.progress ?? []), progress] }
                : item,
            ),
          );
        }
        if (eventName === "delta" && typeof payload.text === "string") {
          setConversation((items) =>
            items.map((item) =>
              item.id === id
                ? { ...item, streamingText: `${item.streamingText ?? ""}${payload.text}` }
                : item,
            ),
          );
        }
        if (eventName === "error") {
          throw new Error(
            typeof payload.detail === "string" ? payload.detail : "Agent stream failed",
          );
        }
        if (eventName === "result") {
          finalPayload = payload as ChatResponse;
          if (finalPayload.session_id) {
            sessionsRef.current[requestActor] = finalPayload.session_id;
          }
          setConversation((items) =>
            items.map((item) =>
              item.id === id
                ? { ...item, response: finalPayload ?? undefined, streamingText: undefined }
                : item,
            ),
          );
        }
      }

      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
        let boundary = buffer.indexOf("\n\n");
        while (boundary >= 0) {
          consumeBlock(buffer.slice(0, boundary));
          buffer = buffer.slice(boundary + 2);
          boundary = buffer.indexOf("\n\n");
        }
        if (done) break;
      }
      if (!finalPayload) throw new Error("Stream ended without a result");
    } catch {
      setConversation((items) =>
        items.map((item) =>
          item.id === id
            ? { ...item, error: "The demo services are unavailable." }
            : item,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void submit(input);
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div>
          <div className="brand">
            <span className="brand-mark">A</span>
            <div>
              <strong>AcmeWorks</strong>
              <span>Operations Copilot</span>
            </div>
          </div>
          <div className="environment">
            <span className="live-dot" />
            Synthetic demo
          </div>
        </div>

        <section className="persona-panel">
          <span className="section-label">DEMO IDENTITY</span>
          <div className="persona-current">
            <span className="avatar">{persona.initials}</span>
            <div>
              <strong>{persona.name}</strong>
              <span>{persona.role}</span>
            </div>
          </div>
          <label htmlFor="persona">Switch role</label>
          <select
            id="persona"
            onChange={(event) => setActorId(Number(event.target.value))}
            value={actorId}
          >
            {PERSONAS.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.role}
              </option>
            ))}
          </select>
          <p>{persona.scope}</p>
        </section>

        <div className="boundary-note">
          <span>SERVER BOUNDARY</span>
          <p>
            Role scope is enforced by the APIs. Every write requires a dry-run
            and a separate confirmation.
          </p>
        </div>
        <PrivacyControls actorId={actorId} key={actorId} />
        <ReportControls actorId={actorId} key={`report-${actorId}`} />
        <AdminControls actorId={actorId} key={`admin-${actorId}`} />
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">WORKFORCE OPERATIONS</span>
            <h1>Ask. Inspect. Confirm.</h1>
          </div>
          <div className="status-pill">
            <span className="live-dot" />
            Demo services connected
          </div>
        </header>

        <div className="conversation">
          {conversation.length === 0 && (
            <section className="welcome">
              <span className="welcome-mark">ACME / 01</span>
              <h2>What would you like to know?</h2>
              <p>
                Query fictional workforce data, inspect every tool call, and
                review proposed changes before anything is written.
              </p>
              <div className="prompt-grid">
                {DEMO_PROMPTS.map((prompt, index) => (
                  <button
                    key={prompt}
                    onClick={() => void submit(prompt)}
                    type="button"
                  >
                    <span>0{index + 1}</span>
                    {prompt}
                  </button>
                ))}
              </div>
            </section>
          )}

          {conversation.map((item) => (
            <article className="exchange" key={item.id}>
              <div className="user-message">
                <span>
                  {PERSONAS.find((candidate) => candidate.id === item.actorId)
                    ?.initials ?? "?"}
                </span>
                <p>{item.prompt}</p>
              </div>
              {item.response && (
                <AssistantResponse
                  actorId={item.actorId}
                  response={item.response}
                />
              )}
              {!item.response && item.streamingText && (
                <div className="assistant-block" aria-live="polite">
                  <div className="assistant-mark">A</div>
                  <div className="assistant-content">
                    <div className="response-meta"><strong>Acme Copilot</strong><span>LLM agent · streaming</span></div>
                    <p className="assistant-message">{item.streamingText}<span className="stream-cursor" aria-hidden="true">▍</span></p>
                  </div>
                </div>
              )}
              {item.error && <div className="error-card">{item.error}</div>}
              {!item.response && !item.error && !item.streamingText && (
                item.progress && item.progress.length > 0 ? (
                  <AgentProgress events={item.progress} />
                ) : (
                  <div className="thinking">
                    <span />
                    <span />
                    <span />
                    Connecting to authorized agent
                  </div>
                )
              )}
            </article>
          ))}
          <div aria-hidden="true" ref={conversationEndRef} />
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <label htmlFor="message">Message Acme Copilot</label>
          <div>
            <textarea
              id="message"
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Ask about projects, hours, or draft a time entry…"
              rows={2}
              value={input}
            />
            <button disabled={busy || !input.trim()} type="submit">
              <span>Send</span>
              <span aria-hidden="true">↗</span>
            </button>
          </div>
          <p>
            Acting as <strong>{persona.name}</strong> · Responses use fictional
            AcmeWorks data only.
          </p>
        </form>
      </section>
    </main>
  );
}
