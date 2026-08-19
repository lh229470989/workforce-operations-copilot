# SMB integration contracts v1

These files are the credential-free machine contracts shared by the Core API and
the two future n8n templates.

- `work-event.schema.json` accepts only the bounded Google Calendar mapping used
  to create a suggestion. It never accepts a raw Calendar payload.
- `confirmed-event.schema.json` contains only the trusted fields allowed to reach
  the Slack notification workflow after an explicit confirmation succeeds.
- `hmac-test-vector.json` freezes exact UTF-8 bytes, SHA-256, HMAC-SHA256 and both
  idempotency hashes. Its key and all fixtures are fictional test-only values.
- `fixtures/` contains synthetic examples and no account identifiers or secrets.

Run the contract suite from `services/demo-core-api`:

```bash
pytest tests/test_integration_contracts.py
```

The 16 KiB HTTP body limit and raw-body signature check happen before JSON parsing
when the ingest endpoint is added. Persistence-backed nonce replay protection and
database idempotency constraints belong to the next implementation batch.
