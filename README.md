# Keel — Customer Digital Twin

Sales + churn as **one twin**. Forge-style **data plane** (DuckDB, raw vs clean, SQL) feeds an unchanged **twin brain**. Same company story as OEE / Forge / PDM — this is the market wall.

```text
upload customers + sales [+ optional behavior]
        │
        ▼
  DuckDB land RAW  →  8-layer CLEAN  →  GOLD join on customer_id
        │
        ▼
  history charts  →  Sales Twin + Churn Twin + Next Best Action
```

Demo CSVs in `data/` load automatically so the dashboard is not empty. Behaviour file is optional: if omitted, inactivity is **derived from last purchase** (logins are not invented).

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.port 8512
```

Upload up to **200 MB** per file (csv / tsv / xlsx). Expand **Data plane** for layer log, raw vs clean, rejects, and a read-only SQL lab.

## CSV contracts

**customers** — `customer_id, name, join_date, segment, region, total_orders`  
**sales** — `customer_id, order_date, amount, product, quantity`  
**behavior** (optional) — `customer_id, last_login, complaints, support_tickets, days_since_last_purchase, email_open_rate`

Aliases like `cust_id`, `₹1,200`, `qty` are cleaned in the pipeline.

## Twin brain (unchanged)

RFM + calibrated HGB for 90d LTV / next purchase / churn %. Decision: Save / Let go / Upsell / Nurture. Discount slider re-scores both heads.

## Tests

```bash
pytest -q
```

## Streamlit Cloud

Repo: [shaikmohammedshoaib666/SALES-CHURN](https://github.com/shaikmohammedshoaib666/SALES-CHURN)  
Deploy: [share.streamlit.io deploy](https://share.streamlit.io/deploy?repository=shaikmohammedshoaib666/SALES-CHURN&branch=main&mainModule=app.py)  
Main file `app.py`, branch `main`. No secrets.

## Honors story

Machine Twin (OEE / Forge / PDM) → **Customer Twin**. Same ingest contract, different user (Sales / CRM).
