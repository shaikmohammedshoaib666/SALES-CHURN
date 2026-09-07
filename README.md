# Keel

Sales + churn as **one Customer Twin**. Left is what they buy (LTV, forecast). Right is whether they leave. Center is the decision — retain with offer X, expand, nurture, or let go.

This repository is in **planning lock**. Read [`docs/PDM-001-keel.md`](docs/PDM-001-keel.md) then [`docs/PDM-002-customer-twin.md`](docs/PDM-002-customer-twin.md). Application code starts only after those memos.

## What Keel is

Keel is a B2B SaaS for the **customer** layer (CRM / CS / marketing decisioning). It does not ship two graphs. Every account is a living twin with two inference heads and one policy.

It is not a Streamlit lab and not a CSV dashboard.

## Standards

Work follows **Forge v2 + PDM** rules, written into PDM-001:

- Spec before code
- Multi-tenant from day one
- Workflows over dashboards
- Explainable risk (drivers, not a mysterious percentage)
- Never commit `.venv`, `.env`, or model binaries

## Status

| Area | State |
| --- | --- |
| Product decision | Accepted |
| Web app | Not started |
| Seed ledger | Specified, not generated |
| Deploy | Not started |

## Local run (after the app exists)

```bash
npm install
cp .env.example .env
npm run dev
```

Optional ML kit (home machine only, later):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r ml/requirements.txt
```

`.venv` stays on your machine. Git gets code and lockfiles only.

## License

Private product source. All rights reserved until published otherwise.
