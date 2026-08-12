# Public Release Checklist

## Automated gates

- [x] `python3 scripts/security_scan.py`
- [x] Core API tests pass.
- [x] AI API tests and authored evaluations pass.
- [x] Web tests, type checking, production build, and browser E2E pass.
- [x] Docker Compose builds and all services become healthy.
- [x] Python and npm dependency audits are reviewed.

## Manual review

- [x] All people, companies, projects, policies, metrics, and screenshots are
      visibly fictional.
- [x] No credentials, tokens, private URLs, IP addresses, local paths, or
      unrelated application content appear in files or screenshots.
- [x] Git history contains only this public demo's authored work.
- [x] Confirmation flows are demonstrated without publishing reusable tokens.
- [x] `SECURITY.md` limitations are accurate.
- [x] The repository is released under the MIT License.

Last verified locally on 2026-08-12. GitHub Actions remains the authoritative
remote gate for each pull request.

Do not publish merely because the automated checks pass. The final content and
Git-history review remains a human release decision.
