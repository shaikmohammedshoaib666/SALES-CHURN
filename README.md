# Keel — Customer Digital Twin

Sales + churn as **one twin**. Forge-style **data plane** (DuckDB, raw vs clean, SQL) feeds an unchanged **twin brain**. Same company story as OEE / Forge / PDM — this is the market wall.

```text
Demo book | upload files | ZIP | Drive / Kaggle / HTTPS URL
        │
        ▼
  DuckDB land RAW  →  SQL slice (time / region / IDs)  →  8-layer CLEAN  →  GOLD
        │
        ▼
  history charts  →  Sales Twin + Churn Twin + Next Best Action
        │
        ▼
  Extended board (presets + region/segment/product filters, 7 charts, no retrain)
```

Demo CSVs in `data/` load automatically so the dashboard is not empty. Behaviour file is optional: if omitted, inactivity is **derived from last purchase** (logins are not invented).

**Large files (~2 GB):** do not upload through the browser (200 MB cap). Put a ZIP or CSV on Google Drive / Kaggle / HTTPS. DuckDB lands the file, you SQL-slice by date / region / customer IDs, and only the slice is cleaned and scored.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.port 8512
```

Sources: demo book; **Upload files** (csv / tsv / xlsx / **zip** per slot, plus an optional ZIP pack); a dedicated ZIP tab; or URLs. A zip named with `customers*.csv` + `sales*.csv` (optional `behavior*.csv`) can stand in for the three files. Browser cap **200 MB**. Expand **Data plane** for layer log, raw vs clean, rejects, and a read-only SQL lab.

## CSV contracts

**customers** — `customer_id, name, join_date, segment, region, total_orders`  
**sales** — `customer_id, order_date, amount, product, quantity`  
**behavior** (optional) — `customer_id, last_login, complaints, support_tickets, days_since_last_purchase, email_open_rate`

Aliases like `cust_id`, `₹1,200`, `qty` are cleaned in the pipeline.

## Twin brain (unchanged)

RFM + calibrated HGB for 90d LTV / next purchase / churn %. Decision: Save / Let go / Upsell / Nurture. Discount slider re-scores both heads.

## Extended board (below the twin)

Does **not** retrain. Time presets (last month / 3 / 6 / 12 months / half year / YTD / custom), period grain (day / week / month), region, segment, product, optional IDs.

- **Sales charts:** over time, per region, by product, top customers, open twin in the window  
- **Customer charts:** twins vs at-risk per region, at-risk LTV per region, play mix  
- Shape row: sales rows×cols, revenue, buyers, twins, customer file shape, date span  

SQL slice at the top still decides who entered the brain. Extended only changes what you look at.

## Write-back lite (does not change the twin)

Under the twin: **action queue CSV** (Save + Upsell by default). Load it into a sheet or Salesforce Data Loader. This app does **not** log into a CRM. Next period, join on `customer_id` to see who still bought.

**Demo AUC:** the 0.89-style score uses **constructed** churn labels on the demo book so the model can be graded. It is not a live CRM “this account left.”

**URLs:** reuse last URLs **this browser session**. Streamlit Cloud has no weekly CRM cron.

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
