import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatWorkspace } from "./ChatWorkspace";

const chartResponse = {
  message: "Here are your role-scoped monthly hours by project.",
  mode: "local",
  tool_events: [
    {
      id: "event-1",
      name: "list_time_entries",
      status: "completed",
      input: {},
      output: [],
    },
  ],
  data: {
    type: "bar",
    title: "Monthly hours by project",
    x_key: "month",
    series_key: "project",
    value_key: "hours",
    rows: [{ month: "2026-07", project: "Apollo", hours: "13.50" }],
  },
  confirmation: null,
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ChatWorkspace", () => {
  it("does not auto-scroll the empty welcome state", () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;

    render(<ChatWorkspace />);

    expect(screen.getByRole("heading", { name: "What would you like to know?" })).toBeVisible();
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it("renders limited Markdown without HTML or actionable model links", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      message: "**Approved steps**\n\n- Inspect `scope`\n- Run:\n\n```sh\necho safe\n```\n\n[Confirm now](https://example.com/action)\n\n<button>Unsafe action</button>",
      mode: "openai", tool_events: [], data: null, confirmation: null,
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const user = userEvent.setup();
    render(<ChatWorkspace />);

    await user.type(screen.getByLabelText("Message Acme Copilot"), "Show formatted guidance");
    await user.click(screen.getByRole("button", { name: /Send/i }));

    expect((await screen.findByText("Approved steps")).tagName).toBe("STRONG");
    expect(screen.getByText("scope").tagName).toBe("CODE");
    expect(screen.getByText("echo safe").tagName).toBe("CODE");
    expect(screen.getByText("Confirm now")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Confirm now" })).not.toBeInTheDocument();
    expect(screen.getByText("Unsafe action")).toBeInTheDocument();
    expect(document.querySelector("button button")).toBeNull();
  });

  it("renders time entries as a readable structured table", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      message: "在你当前角色的权限范围内，共找到 1 条工时记录。",
      mode: "openai", tool_events: [], confirmation: null,
      data: [{ id: 7, employee_id: 3, project_id: 1, project_name: "Apollo",
        work_date: "2026-08-11", hours: "1.25", status: "submitted",
        description: "Validated lifecycle demo" }],
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const user = userEvent.setup(); render(<ChatWorkspace />);
    await user.type(screen.getByLabelText("Message Acme Copilot"), "看下目前所有填的工时");
    await user.click(screen.getByRole("button", { name: /Send/i }));
    const table = await screen.findByRole("region", { name: "Time entries" });
    expect(table).toHaveTextContent("2026-08-11");
    expect(table).toHaveTextContent("Apollo");
    expect(table).toHaveTextContent("Validated lifecycle demo");
  });

  it("renders safe analytics rows and the declarative specification", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      message: "Safe analysis complete.", mode: "local", tool_events: [],
      data: { type: "safe_sql_analysis", dimension: "status", metric: "hours", row_count: 2,
        query_spec: { dimension: "status", metric: "hours", limit: 20 },
        rows: [{ dimension: "approved", value: "7.50" }, { dimension: "submitted", value: "6.00" }] },
      confirmation: null,
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const user = userEvent.setup(); render(<ChatWorkspace />);
    await user.type(screen.getByLabelText("Message Acme Copilot"), "SQL analysis by status");
    await user.click(screen.getByRole("button", { name: /Send/i }));
    expect(await screen.findByRole("region", { name: "Safe analytics result" })).toBeInTheDocument();
    expect(screen.getByText("7.50")).toBeInTheDocument();
    expect(screen.getByText(/NO RAW SQL/)).toBeInTheDocument();
  });

  it("requires a preview and separate confirmation for privacy preferences", async () => {
    const defaults = { actor_id: 3, history_enabled: true, preferred_language: "auto", preferred_project_id: null };
    const changed = { ...defaults, history_enabled: false, preferred_language: "zh" };
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(defaults), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ action: "update_preferences", preview: changed, confirmation_token: "55555555-5555-5555-5555-555555555555" }), { status: 201, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ result: changed }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(changed), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }));
    const user = userEvent.setup(); render(<ChatWorkspace />);
    await user.click(screen.getByText("Privacy & memory"));
    await user.click(screen.getByRole("button", { name: "Load my settings" }));
    await user.click(await screen.findByRole("checkbox"));
    await user.selectOptions(screen.getByLabelText("Reply preference"), "zh");
    await user.click(screen.getByRole("button", { name: "Preview changes" }));
    expect(await screen.findByText(/DRY RUN · update preferences/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    await user.click(screen.getByRole("button", { name: "Explicitly confirm" }));
    expect(await screen.findByText("Preferences saved.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it("keeps simulated Calendar suggestions behind review and confirmation", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([{
        id: "77777777-7777-4777-8777-777777777777",
        source_label: "Google Calendar · simulated",
        status: "suggested",
        project_id: 1,
        project_name: "Apollo",
        work_date: "2026-08-21",
        hours: "1.50",
        description: "Prepared fictional workshop",
        expires_at: "2026-09-04T10:00:00Z",
      }]), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        action: "create_integration_time_entry",
        preview: { source: "Google Calendar · simulated", hours: "1.50" },
        confirmation_token: "88888888-8888-4888-8888-888888888888",
      }), { status: 201, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        action: "create_integration_time_entry",
        result: { id: 42, status: "draft" },
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const user = userEvent.setup();
    render(<ChatWorkspace />);

    await user.click(screen.getByText("Simulated Calendar review"));
    await user.click(screen.getByRole("button", { name: "Load my suggestions" }));
    expect(await screen.findByText("Google Calendar · simulated")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Prepare dry-run" }));
    expect(await screen.findByText("DRY RUN · Calendar suggestion")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await user.click(screen.getByRole("button", { name: "Explicitly confirm" }));
    expect(await screen.findByText(/Time entry confirmed from the simulated/)).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("renders multi-tool comparison rows and deltas", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          message: "Comparison complete.", mode: "local", tool_events: [],
          data: { type: "comparison", baseline: "Apollo", rows: [
            { label: "Apollo", project_name: "Apollo", start_date: "2026-07-20", end_date: "2026-07-22", status: null, entry_count: 2, hours: "13.50", delta_from_first: "0.00" },
            { label: "Beacon", project_name: "Beacon", start_date: "2026-07-20", end_date: "2026-07-22", status: null, entry_count: 0, hours: "0.00", delta_from_first: "-13.50" },
          ]}, confirmation: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const user = userEvent.setup();
    render(<ChatWorkspace />);
    await user.type(screen.getByLabelText("Message Acme Copilot"), "Compare Apollo and Beacon");
    await user.click(screen.getByRole("button", { name: /Send/i }));
    expect(await screen.findByRole("region", { name: "Comparison analysis" })).toBeInTheDocument();
    expect(screen.getByText("-13.50")).toBeInTheDocument();
  });

  it("shows live SSE stages before rendering the final response", async () => {
    const encoder = new TextEncoder();
    const finalResponse = {
      message: "Your profile is Jamie Rivera.",
      mode: "openai",
      session_id: "44444444-4444-4444-4444-444444444444",
      tool_events: [],
      data: null,
      confirmation: null,
    };
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'event: status\ndata: {"stage":"planning","message":"Understanding request"}\n\n',
          ),
        );
        setTimeout(() => {
          controller.enqueue(
            encoder.encode(
              `event: result\ndata: ${JSON.stringify(finalResponse)}\n\nevent: done\ndata: {"ok":true}\n\n`,
            ),
          );
          controller.close();
        }, 300);
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(body, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    const user = userEvent.setup();
    render(<ChatWorkspace />);

    await user.type(screen.getByLabelText("Message Acme Copilot"), "Who am I?");
    await user.click(screen.getByRole("button", { name: /Send/i }));

    expect(await screen.findByRole("region", { name: "Agent progress" })).toBeInTheDocument();
    expect(screen.getByText("Understanding request")).toBeInTheDocument();
    expect(await screen.findByText("Your profile is Jamie Rivera.")).toBeInTheDocument();
  });

  it("reuses a separate short-session id for the selected actor", async () => {
    const response = {
      message: "Your visible projects are: Apollo.",
      mode: "local",
      session_id: "11111111-1111-1111-1111-111111111111",
      context: {
        turn_count: 1,
        actor_role: "employee",
        department_names: ["Product Engineering"],
        recent_project_names: ["Apollo"],
      },
      tool_events: [],
      data: [],
      confirmation: null,
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify(response), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const user = userEvent.setup();
    render(<ChatWorkspace />);
    const composer = screen.getByLabelText("Message Acme Copilot");

    await user.type(composer, "Which projects can I see?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("Your visible projects are: Apollo.");

    await user.type(composer, "What about Beacon?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      actorId: 3,
      message: "What about Beacon?",
      sessionId: "11111111-1111-1111-1111-111111111111",
    });
  });

  it("sends the selected actor and renders tool events and chart data", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify(chartResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const user = userEvent.setup();
    render(<ChatWorkspace />);

    await user.selectOptions(screen.getByLabelText("Switch role"), "2");
    await user.click(
      screen.getByRole("button", {
        name: /Show monthly hours by project as a chart/i,
      }),
    );

    await screen.findByText("13.50");
    expect(screen.getByText("list time entries")).toBeInTheDocument();
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      actorId: 2,
      message: "Show monthly hours by project as a chart.",
    });
  });

  it("renders grounded policy citations", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          message: "Submit by 12:00 noon local time on Monday.",
          mode: "local",
          tool_events: [],
          citations: [
            {
              source_id: "time-reporting",
              title: "AcmeWorks Time Reporting Policy",
              section: "Weekly submission deadline",
              path: "knowledge-base/time-reporting.md",
              excerpt:
                "Employees submit the previous week's time entries by 12:00 noon.",
            },
          ],
          data: null,
          confirmation: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    const user = userEvent.setup();
    render(<ChatWorkspace />);

    await user.click(
      screen.getByRole("button", {
        name: /weekly time submission deadline policy/i,
      }),
    );

    expect(
      await screen.findByRole("region", { name: "Policy sources" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Weekly submission deadline"),
    ).toBeInTheDocument();
  });

  it("renders recent-work suggestions as reviewable candidates", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          message: "I found one suggestion.",
          mode: "openai",
          tool_events: [],
          data: {
            type: "time_entry_suggestions",
            suggestions: [
              {
                project_id: 1,
                project_name: "Apollo",
                target_date: "2026-07-30",
                suggested_hours: "6.00",
                suggested_description: "Validated exports",
                based_on_entry_id: 2,
                based_on_date: "2026-07-21",
              },
            ],
          },
          confirmation: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const user = userEvent.setup();
    render(<ChatWorkspace />);

    await user.type(
      screen.getByLabelText("Message Acme Copilot"),
      "Suggest time entries",
    );
    await user.click(screen.getByRole("button", { name: /Send/i }));

    expect(
      await screen.findByRole("region", { name: "Time entry suggestions" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Validated exports")).toBeInTheDocument();
    expect(screen.getByText(/based on your entry/i)).toBeInTheDocument();
  });

  it("requires a second explicit request before confirming a draft", async () => {
    const confirmationResponse = {
      message: "I prepared a dry-run draft.",
      mode: "local",
      tool_events: [],
      data: null,
      confirmation: {
        action: "create_time_entry",
        preview: {
          employee_name: "Jamie Rivera",
          project_name: "Apollo",
          hours: "2",
        },
        confirmation_token: "11111111-1111-1111-1111-111111111111",
        expires_at: "2026-07-29T12:00:00Z",
        confirm_path:
          "/actions/11111111-1111-1111-1111-111111111111/confirm",
      },
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(confirmationResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 7, status: "draft" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const user = userEvent.setup();
    render(<ChatWorkspace />);

    await user.type(
      screen.getByLabelText("Message Acme Copilot"),
      "Draft 2 hours",
    );
    await user.click(screen.getByRole("button", { name: /Send/i }));

    await screen.findByRole("region", { name: "Confirmation required" });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.click(
      screen.getByRole("button", { name: "Confirm & create" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1][0]).toContain("/api/actions/");
    expect(
      await screen.findByText(/The time entry was created and audited/i),
    ).toBeInTheDocument();
  });

  it("renders and confirms a batch as one explicit action", async () => {
    const batchResponse = {
      message: "I prepared a 2-item batch dry-run.",
      mode: "openai",
      tool_events: [],
      data: null,
      confirmation: {
        action: "create_time_entries",
        preview: {
          count: 2,
          entries: [
            { project_name: "Apollo", hours: "2" },
            { project_name: "Apollo", hours: "3" },
          ],
        },
        confirmation_token: "22222222-2222-2222-2222-222222222222",
        expires_at: "2026-07-29T12:00:00Z",
        confirm_path:
          "/actions/22222222-2222-2222-2222-222222222222/confirm",
      },
    };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(batchResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ result: { count: 2 } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const user = userEvent.setup();
    render(<ChatWorkspace />);

    await user.type(
      screen.getByLabelText("Message Acme Copilot"),
      "Batch draft two entries",
    );
    await user.click(screen.getByRole("button", { name: /Send/i }));

    expect(
      await screen.findByText("Review batch time entry draft"),
    ).toBeInTheDocument();
    expect(screen.getByText(/project_name/)).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Confirm & create" }),
    );
    expect(
      await screen.findByText(/2 time entries were created atomically/i),
    ).toBeInTheDocument();
  });

  it("labels approval dry-runs separately and requires explicit confirmation", async () => {
    const approvalResponse = {
      message: "I prepared an approval dry-run.",
      mode: "local",
      tool_events: [],
      data: null,
      confirmation: {
        action: "decide_time_entry",
        preview: {
          entry_id: 2,
          employee_name: "Jamie Rivera",
          decision: "approved",
        },
        confirmation_token: "33333333-3333-3333-3333-333333333333",
        expires_at: "2026-07-29T12:00:00Z",
        confirm_path:
          "/actions/33333333-3333-3333-3333-333333333333/confirm",
      },
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(approvalResponse), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ result: { time_entry: { status: "approved" } } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    render(<ChatWorkspace />);

    await user.selectOptions(screen.getByLabelText("Switch role"), "2");
    await user.type(
      screen.getByLabelText("Message Acme Copilot"),
      "Approve time entry 2",
    );
    await user.click(screen.getByRole("button", { name: /Send/i }));

    expect(await screen.findByText("Review approval decision")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Confirm decision" }));
    expect(
      await screen.findByText(/time entry was approved and the approval was audited/i),
    ).toBeInTheDocument();
  });
});
