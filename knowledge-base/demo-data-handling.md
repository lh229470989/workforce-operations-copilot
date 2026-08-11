---
id: demo-data-handling
title: AcmeWorks Demo Data Handling Standard
audience: all
reviewed: 2026-07-01
---

# AcmeWorks Demo Data Handling Standard

## Allowed data

The public demonstration uses only fictional AcmeWorks people, departments,
projects, time records, and policies. Users must not enter customer data,
production credentials, private employee information, or confidential source
material into the demo.

## Retention

Conversation context is actor-bound, capped, and expires after the configured
session period. It is stored in the demo's dedicated local SQLite state volume
so an ordinary process restart does not silently erase an active session.

Users may disable history retention. They may also inspect their minimal
language and preferred-project settings, preview deletion of all private demo
state, and explicitly confirm that deletion. Preferences never change access
rights or write-confirmation requirements.

## Exports and screenshots

Before publishing an export or screenshot, verify that it contains only
fictional data and no local file paths, tokens, environment variables, or
unrelated application content.
