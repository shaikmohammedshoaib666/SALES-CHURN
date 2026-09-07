# Keel

Sales + churn operating system. Pipeline, MRR ledger, and an explainable risk queue in one workspace.

This repository is in **planning lock**. The product decision is [`docs/PDM-001-keel.md`](docs/PDM-001-keel.md). Application code starts only after that memo.

## What Keel is

Keel is a B2B SaaS product for founder-led teams who need to see **what they sold**, **what is leaking**, and **who works the risk** — without stitching a CRM, a spreadsheet, and a churn notebook.

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
