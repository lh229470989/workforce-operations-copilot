"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { DEMO_PROMPTS, PERSONAS } from "@/lib/personas";
import type {
  ChartData,
  ChatResponse,
  Confirmation,
  ConversationItem,
  PolicyCitation,
  ToolEvent,
} from "@/lib/types";

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

function PreviewValue({ value }: { value: unknown }) {
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
    onResolved("Confirmed. The time entry was created and audited.");
  }

  if (state === "cancelled") {
    return <div className="resolution-note">Draft dismissed. No write was made.</div>;
  }

  return (
    <section className="confirmation-card" aria-label="Confirmation required">
      <div className="confirmation-head">
        <div className="shield">✓</div>
        <div>
          <span className="eyebrow">EXPLICIT CONFIRMATION REQUIRED</span>
          <h3>Review time entry draft</h3>
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
            {response.mode} planner
            {response.context
              ? ` · ${response.context.turn_count} turn context`
              : ""}
          </span>
        </div>
        <p className="assistant-message">{response.message}</p>
        {response.citations && response.citations.length > 0 && (
          <CitationList citations={response.citations} />
        )}
        {isChartData(response.data) && <HoursChart chart={response.data} />}
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
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actorId: requestActor,
          message: trimmed,
          sessionId: sessionsRef.current[requestActor],
        }),
      });
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
              {item.error && <div className="error-card">{item.error}</div>}
              {!item.response && !item.error && (
                <div className="thinking">
                  <span />
                  <span />
                  <span />
                  Checking authorized data
                </div>
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
