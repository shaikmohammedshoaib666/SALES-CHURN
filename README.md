# Keel

Sales + churn as **one Customer Twin**. Left is what they buy (LTV, forecast). Right is whether they leave. Center is the decision — retain with offer X, expand, nurture, or let go.

This repository is in **planning lock**. Read PDM-001, PDM-002, then [`docs/PDM-003-implementation.md`](docs/PDM-003-implementation.md). The build stack is React + Vite + Tailwind + Recharts + CSV ingest. Application code starts only after you say go.

## What Keel is

A **Customer Digital Twin** platform for any product book of business. Upload sales + behavioral CSVs; every `customer_id` becomes one twin (sales + churn + decision). That is the same Forge / PDM pipeline pointed at the customer, after OEE (factory) and Forge (product).

CSV is the **ingest adapter**, not the product. The product is the twin.

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
| Product decision | Accepted (PDM-001, 002, 003) |
| Web app | Not started (React + Vite, on go) |
| Seed ledger | Specified, not generated |
| Deploy | Not started |

## Local run (after the app exists)

```bash
npm install
npm run dev
```

Upload `sales.csv` + `churn.csv`, or use the shipped demo book. Optional `product` column is affinity; any industry catalog works.

Optional ML kit (home machine only, later):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r ml/requirements.txt
```

`.venv` stays on your machine. Git gets code and lockfiles only.

## License

Private product source. All rights reserved until published otherwise.
