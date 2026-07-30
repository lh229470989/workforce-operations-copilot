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
});
