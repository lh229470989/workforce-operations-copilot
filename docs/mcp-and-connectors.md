# MCP and connector boundaries

The portfolio service includes one first-party MCP server backed only by the
fictional Core API. This demonstrates an external Agent integration without
granting a model direct database or confirmation access.

```text
MCP host/model → AcmeWorks MCP → Demo Core API → scoped SQLAlchemy query → SQLite
                         └──── dry-run only; trusted UI owns confirmation
```

Every connector should implement the same three boundaries:

1. **Identity adapter** maps a verified principal to an internal actor. The
   explicit numeric actor selector is demo-only and must not be copied to a
   production connector.
2. **Read adapter** returns normalized business objects after upstream and
   local authorization. It does not accept raw SQL or arbitrary URLs.
3. **Action adapter** prepares an idempotent preview. A trusted user interface,
   not an LLM tool call, owns the separate confirmation credential.

Future calendar, ticketing, or HRIS integrations should live in independent
services and call stable Core/AI contracts. Secrets belong in runtime secret
storage, scopes should be least-privilege, and logs must retain metadata rather
than message bodies or business records. The demo intentionally does not attach
real Google, Slack, Jira, HR, or payroll accounts.

MCP tool annotations distinguish read-only tools from preview tools. The
service exports resources and prompts for discovery, but none of those objects
can expand role scope. Protocol tests verify the catalog, structured results,
identity forwarding, safe error normalization, and confirmation-token hiding.
