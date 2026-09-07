# Keel — Customer Digital Twin

Sales + churn as **one twin**, same CSV→join→dashboard pattern as OEE Pulse, pointed at the market wall.

Factory team uses OEE / Forge / PDM (machine health). Business team uses Keel (customer health). Same company, no gap.

```text
customers.csv  (master — who they are)
sales.csv      (purchase sensors — what they bought)
behavior.csv   (live health — will they leave)
        │
        ▼
   join on customer_id
        │
        ▼
  Historical charts  →  Twin prediction (next buy + churn % + next best action)
```

## Run locally

Python 3.11+. Do **not** commit `.venv` — create it on your machine:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.data                 # writes data/*.csv if missing
streamlit run app.py --server.port 8512
```

Open the URL Streamlit prints. Demo book loads automatically. Or upload your own three CSVs with the columns below.

## CSV contracts (OEE-style)

**customers.csv** — master / history

`customer_id, name, join_date, segment, region, total_orders`

**sales.csv** — transactions / purchase sensors

`customer_id, order_date, amount, product, quantity`

**behavior.csv** — live churn signals

`customer_id, last_login, complaints, support_tickets, days_since_last_purchase, email_open_rate`

Any industry catalog works. `product` is just a SKU name.

## What the models do

- **Sales Twin:** RFM on the joined purchase history + HistGradientBoosting for 90-day LTV and next purchase date. LTV is **risk-adjusted** with the churn probability from the same clock.
- **Churn Twin:** behavioral decay (silence, tickets, complaints, email) + **calibrated** HGB classifier → churn %, reason (Price / Service / Inactivity), health 0–100.
- **Brain:** High sales × high risk = Save with Premium Offer; low × high = Let go; high × low = Upsell; else Nurture.
- **Simulation:** discount slider re-scores both heads live.

## Tests

```bash
pytest -q
```

## Deploy on Streamlit Community Cloud

1. Create a GitHub repo from this project (New Project → **Create repo**).
2. [share.streamlit.io](https://share.streamlit.io) → New app → this repo → `main` → `app.py`.
3. Deploy. No secrets required. Demo CSVs ship in `data/`.

`.venv` is local-only. Cloud installs from `requirements.txt`.

## Honors story

Machine Twin (OEE / Forge / PDM) → Product Twin → **Customer Twin**. Same join discipline, different user (Sales Head / CRM, not the factory manager).
