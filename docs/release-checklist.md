# Public Release Checklist

## Automated gates

- [ ] `python3 scripts/security_scan.py`
- [ ] Core API tests pass.
- [ ] AI API tests and authored evaluations pass.
- [ ] Web tests, type checking, and production build pass.
- [ ] Docker Compose builds and all services become healthy.
- [ ] Python and npm dependency audits are reviewed.

## Manual review

- [ ] All people, companies, projects, policies, metrics, and screenshots are
      visibly fictional.
- [ ] No credentials, tokens, private URLs, IP addresses, local paths, or
      unrelated application content appear in files or screenshots.
- [ ] Git history contains only this public demo's authored work.
- [ ] Confirmation flows are demonstrated without publishing reusable tokens.
- [ ] `SECURITY.md` limitations are accurate.
- [ ] A publication license has been chosen by the repository owner.

Do not publish merely because the automated checks pass. The final content and
Git-history review remains a human release decision.
