# Prompt versioning

The planner and composer prompts are original AcmeWorks assets loaded from
`manifest.json`. Application startup verifies each file's SHA-256 digest and
fails closed on unreviewed drift.

To publish a prompt change:

1. Copy the current prompt to a new immutable filename such as
   `planner-v1.1.txt`; do not rewrite a released version in place.
2. Review the safety boundary and run the AI evaluation suite.
3. Calculate `shasum -a 256 <file>` and update the manifest's semantic version,
   filename, and digest together.
4. Run `pytest`, the publication security scan, and a real provider smoke test.

The `/health` and `/ready` responses expose versions, never prompt content.
Rollback means pointing the manifest to a previously reviewed file and digest.
