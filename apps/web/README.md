# AcmeWorks Web

This Next.js workspace is the browser UI for the fully fictional AcmeWorks
demo. It provides:

- employee, manager, and admin demo-persona switching;
- chat prompt shortcuts and a free-form composer;
- visible tool-event cards;
- live planning, authorized-tool, and answer-composition status over SSE;
- role-scoped monthly-hours charts;
- personal time-entry suggestion cards;
- single and batch dry-run review cards with a separate explicit confirmation
- a clearly labeled simulated Calendar suggestion review that still requires a
  server-side dry-run and separate confirmation
  button;
- distinct approval/rejection review cards for authorized managers and admins;
- weekly report summaries with a role-scoped CSV download;
- comparison tables showing per-slice hours and deltas from the first slice;
- privacy controls for bounded history, language/project preferences, and
  two-step private-state deletion;
- safe analytics tables that expose the validated specification, never SQL text;
- actor-specific short conversation sessions for safe follow-up questions.

The browser calls local Next.js route handlers. Those handlers forward only a
known demo actor ID to the FastAPI services; the Core API remains the
authorization boundary.

The streaming route proxies FastAPI's response body without buffering. The UI
shows only safe stage and tool-name metadata while work is running, then renders
the unchanged structured response used by charts, citations, and confirmation
cards.

## Run with the full stack

From the repository root:

```bash
docker compose up --build
```

Open `http://localhost:3000`.

## Run locally

Keep the APIs running on ports 8000 and 8001, then:

```bash
npm install
npm run dev
```

## Verify

```bash
npm test
npm run typecheck
npm run build
```

Recommended manual scenarios:

1. As Jamie Rivera, ask `Who am I?`, `List employees`, and
   `Show my last 5 submitted time entries`.
2. Ask for Apollo project members, then Apollo hours this week.
3. Request the monthly chart and expand both tool-event cards.
4. Switch to Morgan Lee and compare `List employees` with Jamie's result, then
   ask about pending approvals.
5. As Jamie, request an exact time-entry draft. Check that the preview says
   `DRY RUN`, then either dismiss it or explicitly confirm it.
6. Ask for today's time-entry suggestions and verify no confirmation card is
   created. Then request two explicit batch entries and verify one review card
   lists both entries before confirmation.
7. As Morgan, inspect pending entries, then request approval for one exact ID.
   Verify the decision remains unchanged until `Confirm decision` is clicked.
