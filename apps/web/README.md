# AcmeWorks Web

This Next.js workspace is the browser UI for the fully fictional AcmeWorks
demo. It provides:

- employee, manager, and admin demo-persona switching;
- chat prompt shortcuts and a free-form composer;
- visible tool-event cards;
- role-scoped monthly-hours charts;
- a dry-run review card with a separate explicit confirmation button.
- actor-specific short conversation sessions for safe follow-up questions.

The browser calls local Next.js route handlers. Those handlers forward only a
known demo actor ID to the FastAPI services; the Core API remains the
authorization boundary.

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
