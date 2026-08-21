# n8n 2.34.6 integration templates

These disabled, credential-free templates demonstrate the private integration path:

- `workflow-a-calendar-ingest.json`: read a dedicated Google Calendar with a
  `calendar.readonly` credential, map explicitly marked events to `WorkEvent v1`,
  sign the exact body, and create a reviewable suggestion.
- `workflow-b-confirmed-slack.json`: verify a raw confirmed-event webhook, obtain
  a persistent one-time delivery claim, send a fixed Slack Incoming Webhook
  message, and complete the delivery ledger.

They are intended for self-hosted n8n `2.34.6`. They contain no credentials,
account IDs, hostnames, webhook secrets, or real data and remain disabled after
import. The public application does not run these workflows.

## Import and configure

1. Import each JSON into a blank n8n `2.34.6` instance.
2. Attach a Google Calendar OAuth credential to Workflow A. The granted scope
   must be exactly `https://www.googleapis.com/auth/calendar.readonly` and the
   credential must belong to the isolated test-only Google project.
3. Permit the Code node to use Node's built-in `crypto` module. For a standard
   self-hosted deployment set `NODE_FUNCTION_ALLOW_BUILTIN=crypto`.
4. Inject the following through the n8n runtime environment or external secret
   store; never save their resolved values back into an exported template:

| Variable | Workflow | Purpose |
| --- | --- | --- |
| `GOOGLE_CALENDAR_ID` | A | Dedicated test Calendar selected by the Google node |
| `GOOGLE_SOURCE_ACCOUNT_REF` | A | Non-email allowlisted source alias |
| `GOOGLE_CALENDAR_REF` | A | Non-secret allowlisted Calendar alias sent to Copilot |
| `COPILOT_INGEST_URL` | A | Exact private ingest endpoint |
| `COPILOT_INGEST_HMAC_SECRET` | A | Ingest signing secret |
| `COPILOT_OUTBOUND_HMAC_SECRET` | B | Copilot-to-n8n verification secret |
| `COPILOT_OUTBOUND_WEBHOOK_PATH` | B | Exact webhook path used in the outbound signature |
| `COPILOT_CORE_BASE_URL` | B | Private Core API origin |
| `COPILOT_NOTIFICATION_CALLBACK_HMAC_SECRET` | B | Claim/complete signing secret |
| `SLACK_CHANNEL_REF` | B | Non-secret allowlisted channel alias |
| `SLACK_WEBHOOK_URL` | B | Secret Incoming Webhook URL |

5. Create only fictional Calendar events. An accepted event must have these
   private extended properties: `acme_work_event=v1`, `person_ref`,
   `project_code`, and `work_description`. Attendees, descriptions, conference
   data and unknown properties are discarded.
6. Run each workflow manually with fixtures first. Activate Workflow A only after
   the server-side source/person/project allowlists are configured. Activate
   Workflow B only after its raw-body signature vector and delivery claim pass.

The HTTP nodes intentionally have no fallback URL. Missing runtime variables or
credentials stop execution clearly. Workflow A never waits for or performs human
confirmation. Workflow B cannot reach Slack unless signature validation and the
Copilot delivery claim both succeed.

## Validation

```bash
python scripts/scan_n8n_templates.py
docker run --rm -v "$PWD/integrations/n8n:/templates:ro" n8nio/n8n:2.34.6 \
  import:workflow --separate --input=/templates
```

The repository scanner verifies graph ordering, the credential-free export,
runtime-only secret references, the bounded mapping, and prohibited-value rules.
The Docker import check validates the serialized format against the locked n8n
version. Runtime calls are covered without third-party credentials by the Core API
contract and mock tests.

## Failure and recovery

- `401 invalid_signature`: disable the workflow, compare its fixed vector, then
  rotate the affected active/next secret. Never retry the same nonce.
- Google `401/403`: keep the workflow disabled until the isolated OAuth credential
  and exact read-only scope are restored.
- deterministic `4xx` from ingest: correct the fictional event or server mapping;
  do not retry automatically.
- `429` or temporary `5xx`: honor `Retry-After` or use bounded `2s/4s/8s` retries
  with jitter and the same idempotency key.
- Slack timeout after request transmission, or a crash before completion: treat
  the claim as `delivery_unknown`. Check the dedicated channel manually before
  creating any explicit new attempt.
- leaked Slack URL or HMAC secret: revoke/rotate it, inspect minimal audit metadata,
  update the secret store, then reactivate. Do not edit the public JSON.

To reset a private demo, deactivate both workflows, delete only the fictional
Calendar events and dedicated test-channel messages, clear the application's test
database, rotate temporary secrets, then replay the versioned fixtures.
