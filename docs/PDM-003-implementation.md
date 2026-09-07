# PDM-003 — Implementation lock (meta Customer Twin prompt)

**Status:** Accepted (pre-build). Does not replace PDM-001 or PDM-002. It is how we **build** them.  
**Owner:** CEO  
**Depends on:** PDM-001, PDM-002  
**Build:** still not started.

The meta prompt is the implementation spec. Use it as-is. Previous requirements stay: Forge-style pipeline, any-industry sales data, one twin per customer, no `.venv` in git, new repo only (do not touch Forge / OEE / PDM repos).

---

## 1. What stays from 001 / 002

- One identity → one twin → sales lobe + churn lobe + decision.
- Same `as_of` clock. Risk-adjusted value (sales uses churn).
- Closed loop: simulate / act / write back.
- Industry 4.0 continuity: OEE (factory) → Forge (product) → this (customer).
- Works for **any product book**: CSV is the adapter. Columns map; the twin does not care if the SKU is seats, spare parts, or SKUs on a shelf.
- Optional `product` column for affinity; required sales keys still `customer_id, last_purchase, frequency, amount`.

## 2. What the prompt adds (now binding)

| Item | Lock |
| --- | --- |
| Stack | React + Vite + TypeScript + Tailwind + Recharts + CSV upload |
| Hero UI | Twin 360: profile left, twin visualization center, risk meter right |
| Sales head | RFM → next purchase date, 90d LTV, affinity, trend |
| Churn head | Behavioral decay → P(churn), reason (Price / Service / Inactivity), health 0–100, at-risk |
| Brain | 2×2: Save with Premium Offer / Let go / Upsell-Loyalty / (implied nurture) + NBA card |
| Simulation | Discount slider → live churn ↓ and LTV ↑ |
| Finish | Dark glass, pulse, PDF twin report |
| Seed files | `sales.csv`, `churn.csv` as specified; demo file ships so faculty can run without upload |

## 3. What we still refuse

- Two models, two pages, two graphs as the product.
- Streamlit as the surface.
- Committing `.venv`.
- Opening any existing GitHub project (Forge, PDM, OEE). This is a new repo.

## 4. Pipeline (canonical — same spine as Forge / PDM)

See the explanation delivered with this memo. Stages: Ingest → Identity → RFM Sales Twin → Decay Churn Twin → Unified Brain → Simulate → Report.

Do not start code until the operator says go.
