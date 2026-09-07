"""Keel Customer Twin — Streamlit 360. Historical CSVs in, future twin out."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.brain import score_book, simulate_discount
from src.data import DATA_DIR, TwinBook, write_demo
from src.history import customer_history, monthly_risk, monthly_sales
from src.landing import DuckLanding, absorb_zip, default_slice_sql, land_from_collected, land_paths, land_zip_file
from src.models import TwinModels, train_twin_models
from src.pipeline import LAYER_CONTRACT, read_tabular, run_pipeline
from src.report import twin_pdf
from src.twin import CustomerTwin, twin_from_row
from src.url_ingest import resolve_source
from src.warehouse import run_sql

st.set_page_config(
    page_title="Keel · Customer Twin",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.block-container { padding-top: 1.2rem; max-width: 1400px; }
header { visibility: hidden; }
.hero {
  background: linear-gradient(135deg, rgba(45,212,191,0.12), rgba(14,165,233,0.08));
  border: 1px solid rgba(45,212,191,0.25);
  border-radius: 18px; padding: 18px 22px; margin-bottom: 12px;
}
.hero h1 { color: #F8FAFC; font-size: 1.55rem; margin: 0 0 4px 0; letter-spacing: -0.03em; }
.hero p { color: #94A3B8; margin: 0; font-size: 0.92rem; }
.glass {
  background: rgba(15,23,42,0.72);
  border: 1px solid rgba(148,163,184,0.18);
  border-radius: 16px; padding: 16px 18px; margin-bottom: 10px;
}
.pulse-ring {
  width: 168px; height: 168px; margin: 8px auto;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 50%, rgba(45,212,191,0.35), rgba(7,11,20,0.9) 62%);
  box-shadow: 0 0 0 0 rgba(45,212,191,0.45);
  animation: pulse 2.4s infinite;
  display: flex; align-items: center; justify-content: center; flex-direction: column;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(45,212,191,0.45); }
  70% { box-shadow: 0 0 0 18px rgba(45,212,191,0); }
  100% { box-shadow: 0 0 0 0 rgba(45,212,191,0); }
}
.ring-val { font-size: 2rem; font-weight: 700; color: #F8FAFC; }
.ring-lbl { font-size: 0.75rem; color: #94A3B8; letter-spacing: 0.12em; text-transform: uppercase; }
.nba {
  background: linear-gradient(180deg, rgba(251,191,36,0.12), rgba(15,23,42,0.9));
  border: 1px solid rgba(251,191,36,0.35);
  border-radius: 16px; padding: 16px 18px;
}
.nba h3 { margin: 0 0 6px 0; color: #FBBF24; font-size: 1.05rem; }
.ok { color: #2DD4BF; } .bad { color: #FB7185; } .warn { color: #FBBF24; }
div[data-testid="stMetric"] {
  background: rgba(15,23,42,0.8); border: 1px solid rgba(148,163,184,0.16);
  border-radius: 14px; padding: 10px 12px;
}
</style>
"""


def _sig(customers: pd.DataFrame, sales: pd.DataFrame, behavior: pd.DataFrame) -> str:
    blob = (
        pd.util.hash_pandas_object(customers, index=True).to_numpy().tobytes()
        + pd.util.hash_pandas_object(sales, index=True).to_numpy().tobytes()
        + pd.util.hash_pandas_object(behavior, index=True).to_numpy().tobytes()
    )
    return hashlib.sha1(blob).hexdigest()


def _dark(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#CBD5E1", family="IBM Plex Sans"),
        margin=dict(l=16, r=12, t=36, b=16),
        height=280,
        legend=dict(orientation="h", y=1.12),
    )
    fig.update_xaxes(gridcolor="rgba(148,163,184,0.12)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.12)", zeroline=False)
    return fig


def _parse_ids(text: str) -> list[str]:
    return [p.strip() for p in text.replace(",", "\n").splitlines() if p.strip()]


def _write_tmp(uploaded, suffix: str) -> Path:
    tmp = Path(tempfile.mkstemp(prefix="keel-up-", suffix=suffix)[1])
    tmp.write_bytes(uploaded.getvalue())
    return tmp


def _is_zip_upload(uploaded) -> bool:
    return str(getattr(uploaded, "name", "")).lower().endswith(".zip")


def _land_from_ui() -> tuple[DuckLanding, str]:
    if not (DATA_DIR / "customers.csv").exists():
        write_demo()
    source = st.radio(
        "How data enters DuckDB",
        ["Demo book", "Upload files", "Upload ZIP", "URL (Drive / Kaggle / HTTPS)"],
        horizontal=True,
    )
    if source == "Demo book":
        land = land_paths(
            {
                "customers": str(DATA_DIR / "customers.csv"),
                "sales": str(DATA_DIR / "sales.csv"),
                "behavior": str(DATA_DIR / "behavior.csv"),
            }
        )
        return land, "demo book"
    if source == "Upload files":
        st.caption(
            "ZIP pack, or customers + sales as csv / tsv / xlsx / zip. "
            "A ZIP dropped on any slot can hold the whole pack. Browser max ~200 MB."
        )
        pack = st.file_uploader(
            "ZIP pack (optional) — customers*.csv + sales*.csv (+ behavior*.csv)",
            type=["zip"],
            key="pack",
        )
        c1, c2, c3 = st.columns(3)
        kinds = ["csv", "tsv", "xlsx", "zip"]
        up_c = c1.file_uploader("customers (master)", type=kinds, key="c")
        up_s = c2.file_uploader("sales (purchases)", type=kinds, key="s")
        up_b = c3.file_uploader("behavior (optional)", type=kinds, key="b")
        collected: dict = {}
        try:
            if pack is not None:
                absorb_zip(collected, _write_tmp(pack, ".zip"))
            for feed, up in (("customers", up_c), ("sales", up_s), ("behavior", up_b)):
                if up is None:
                    continue
                if _is_zip_upload(up):
                    absorb_zip(collected, _write_tmp(up, ".zip"), slot=feed)
                else:
                    collected[feed] = read_tabular(up)
        except Exception as exc:
            st.error(str(exc))
            st.stop()
        if "customers" not in collected or "sales" not in collected:
            st.info("Need customers + sales — two files, or one ZIP that contains both.")
            st.stop()
        return land_from_collected(collected), "upload files"
    if source == "Upload ZIP":
        z = st.file_uploader("ZIP with customers*.csv + sales*.csv (+ behavior*.csv)", type=["zip"], key="zip")
        st.caption("Browser ZIP max ~200 MB. For ~2 GB use a Drive/Kaggle/HTTPS link below.")
        if z is None:
            st.stop()
        tmp = Path(tempfile.mkstemp(prefix="keel-zip-", suffix=".zip")[1])
        tmp.write_bytes(z.getvalue())
        return land_zip_file(tmp), "zip"
    st.caption(
        "DuckDB reads the file; SQL slice runs *before* pandas/clean/twin. "
        "Kaggle dataset pages need KAGGLE_USERNAME + KAGGLE_KEY secrets, or paste a direct file URL."
    )
    u_c = st.text_input("Customers URL")
    u_s = st.text_input("Sales URL (or a single ZIP URL in this box and leave others empty)")
    u_b = st.text_input("Behavior URL (optional)")
    if not u_s.strip():
        st.info("Paste at least a sales CSV/Parquet/ZIP URL.")
        st.stop()
    if not u_c.strip():
        path, _meta = resolve_source(u_s.strip())
        peek = Path(path)
        if str(path).lower().endswith(".zip") or zipfile_is_zip(peek):
            return land_zip_file(peek), "url-zip"
        raise ValueError("Customers URL is required unless the sales URL is a ZIP that contains both files.")
    paths: dict[str, str] = {}
    if u_c.strip():
        paths["customers"], _ = resolve_source(u_c.strip())
    paths["sales"], _ = resolve_source(u_s.strip())
    if u_b.strip():
        paths["behavior"], _ = resolve_source(u_b.strip())
    return land_paths(paths), "url"


def zipfile_is_zip(path: Path) -> bool:
    import zipfile

    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def _ingest() -> TwinBook:
    st.markdown(
        '<div class="hero"><h1>Customer Digital Twin</h1>'
        "<p>Land in DuckDB (files / ZIP / Drive-Kaggle URL) → SQL slice by time, region, IDs "
        "→ clean layers → unchanged twin brain. 2 GB stays in the warehouse; only the slice is scored.</p></div>",
        unsafe_allow_html=True,
    )
    try:
        land, source = _land_from_ui()
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    n_c, n_s, n_b = land.rowcount("customers"), land.rowcount("sales"), land.rowcount("behavior")
    k1, k2, k3 = st.columns(3)
    k1.metric("DuckDB customers (raw)", f"{n_c:,}")
    k2.metric("DuckDB sales (raw)", f"{n_s:,}")
    k3.metric("DuckDB behaviour (raw)", f"{n_b:,}")

    st.markdown("##### SQL slice — choose what enters clean + twin")
    s1, s2, s3 = st.columns(3)
    date_from = s1.text_input("Sales from (YYYY-MM-DD)", "2024-01-01")
    date_to = s2.text_input("Sales to (YYYY-MM-DD)", "2026-09-07")
    id_text = s3.text_area("Customer IDs (optional, comma or newline)", height=70)
    regions_avail = land.distinct("customers", "region") or land.distinct("sales", "region")
    regions = st.multiselect("Regions (optional)", options=regions_avail, default=[])
    advanced = st.checkbox("Advanced: write SQL per feed (overrides date/region/ID filters)")
    sql_c = sql_s = sql_b = ""
    if advanced:
        sql_c = st.text_area("Slice customers", value=default_slice_sql("customers"), height=90)
        sql_s = st.text_area("Slice sales", value=default_slice_sql("sales"), height=90)
        sql_b = st.text_area("Slice behavior", value=default_slice_sql("behavior"), height=90) if "behavior" in land.feeds else ""

    apply = st.button("Apply slice → clean → twin", type="primary")
    if not apply and source != "demo book":
        st.info("Landed in DuckDB. Set the slice, then apply. Demo book auto-runs a default slice.")
        st.stop()

    try:
        ids = _parse_ids(id_text)
        if advanced and sql_s.strip():
            sales_df = land.slice_sql(sql_s)
            customers_df = land.slice_sql(sql_c) if sql_c.strip() else land.slice_sql("SELECT * FROM raw_customers LIMIT 100000")
            behavior_df = land.slice_sql(sql_b) if sql_b.strip() and "behavior" in land.feeds else None
        else:
            sales_df = land.slice_sales(
                date_from=date_from or None,
                date_to=date_to or None,
                regions=list(regions) or None,
                customer_ids=ids or None,
            )
            if ids:
                listed = ", ".join("'" + i.replace("'", "''") + "'" for i in ids)
                customers_df = land.slice_sql(
                    f"SELECT * FROM raw_customers WHERE CAST(customer_id AS VARCHAR) IN ({listed}) LIMIT 100000"
                )
            elif regions:
                listed = ", ".join("'" + r.replace("'", "''") + "'" for r in regions)
                try:
                    customers_df = land.slice_sql(
                        f"SELECT * FROM raw_customers WHERE CAST(region AS VARCHAR) IN ({listed}) LIMIT 100000"
                    )
                except Exception:
                    customers_df = land.slice_sql("SELECT * FROM raw_customers LIMIT 100000")
            else:
                customers_df = land.slice_sql("SELECT * FROM raw_customers LIMIT 100000")
            if "behavior" in land.feeds:
                if ids:
                    listed = ", ".join("'" + i.replace("'", "''") + "'" for i in ids)
                    behavior_df = land.slice_sql(
                        f"SELECT * FROM raw_behavior WHERE CAST(customer_id AS VARCHAR) IN ({listed}) LIMIT 100000"
                    )
                else:
                    behavior_df = land.slice_sql("SELECT * FROM raw_behavior LIMIT 100000")
            else:
                behavior_df = None
        pipe = run_pipeline(customers_df, sales_df, behavior_df)
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    book = pipe.book
    st.session_state["pipeline"] = pipe
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Sliced master", f"{len(pipe.customers.raw):,}")
    m2.metric("Sliced sales", f"{len(pipe.sales.raw):,}")
    m3.metric("Twins (gold)", f"{len(book.panel):,}")
    n_rej = len(pipe.customers.rejects) + len(pipe.sales.rejects) + len(pipe.behavior.rejects)
    m4.metric("Reject rows", f"{n_rej:,}")
    m5.metric("Behaviour", "inferred" if pipe.behavior_source == "inferred_from_sales" else "uploaded")
    st.caption(f"Source: {source} · DuckDB slice then clean · unmatched {book.dropped_ids:,} · {pipe.gold_note}")

    with st.expander("Data plane · layers · raw vs clean · SQL lab", expanded=False):
        st.write("Contract: land → SQL slice → " + " → ".join(LAYER_CONTRACT))
        st.dataframe(pipe.layer_rows, use_container_width=True, hide_index=True)
        t1, t2, t3, t4 = st.tabs(["Raw vs clean", "Rejects", "SQL lab (clean tables)", "Gold panel"])
        with t1:
            feed = st.selectbox("Feed", ["customers", "sales", "behavior"])
            left, right = st.columns(2)
            raw_map = {"customers": pipe.customers.raw, "sales": pipe.sales.raw, "behavior": pipe.behavior.raw}
            clean_map = {"customers": pipe.customers.clean, "sales": pipe.sales.clean, "behavior": pipe.behavior.clean}
            left.caption("SLICE entering clean")
            left.dataframe(raw_map[feed].head(40), use_container_width=True)
            right.caption("CLEAN")
            right.dataframe(clean_map[feed].head(40), use_container_width=True)
        with t2:
            st.dataframe(pipe.customers.rejects.head(30), use_container_width=True)
            st.dataframe(pipe.sales.rejects.head(30), use_container_width=True)
            st.dataframe(pipe.behavior.rejects.head(30), use_container_width=True)
        with t3:
            default_sql = (
                "SELECT customer_id, COUNT(*) AS orders, SUM(amount) AS revenue "
                "FROM clean_sales GROUP BY 1 ORDER BY revenue DESC LIMIT 20"
            )
            sql = st.text_area("Read-only SQL (DuckDB)", value=default_sql, height=90)
            if st.button("Run SQL"):
                try:
                    result, engine = run_sql(sql, pipe.tables)
                    st.caption(f"engine: {engine}")
                    st.dataframe(result, use_container_width=True)
                except Exception as exc:
                    st.error(str(exc))
        with t4:
            st.dataframe(book.panel.head(40), use_container_width=True)
    return book


def _models(book: TwinBook) -> TwinModels:
    sig = _sig(book.customers, book.sales, book.behavior)
    if st.session_state.get("model_sig") != sig:
        with st.spinner("Fitting calibrated HGB twin heads (churn + LTV + next purchase)…"):
            st.session_state.models = train_twin_models(book.panel)
            st.session_state.model_sig = sig
    return st.session_state.models


def _history_charts(book: TwinBook) -> None:
    sales_m = monthly_sales(book.sales)
    risk_m = monthly_risk(book.sales)
    left, right = st.columns(2)
    fig = go.Figure()
    fig.add_bar(x=sales_m["month"], y=sales_m["revenue"], name="Revenue", marker_color="#2DD4BF")
    fig.add_scatter(
        x=sales_m["month"],
        y=sales_m["ltv_cum"],
        name="Cumulative LTV",
        yaxis="y2",
        line=dict(color="#38BDF8", width=2.5),
    )
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, title="Cumulative"))
    fig.update_layout(title="Sales history · 12 months (purchase sensors)")
    left.plotly_chart(_dark(fig), use_container_width=True)

    fig2 = go.Figure()
    fig2.add_scatter(
        x=risk_m["month"],
        y=risk_m["risk"] * 100,
        fill="tozeroy",
        name="Silent > 45d %",
        line=dict(color="#FB7185", width=2.5),
    )
    fig2.update_layout(title="Reconstructed churn pressure · month-end silence")
    right.plotly_chart(_dark(fig2), use_container_width=True)


def _gauge(p_churn: float) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=p_churn * 100,
            number={"suffix": "%", "font": {"size": 28, "color": "#F8FAFC"}},
            title={"text": "Churn twin", "font": {"size": 13, "color": "#94A3B8"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#64748B"},
                "bar": {"color": "#FB7185" if p_churn >= 0.45 else "#2DD4BF"},
                "bgcolor": "rgba(15,23,42,0.4)",
                "steps": [
                    {"range": [0, 28], "color": "rgba(45,212,191,0.25)"},
                    {"range": [28, 45], "color": "rgba(251,191,36,0.25)"},
                    {"range": [45, 100], "color": "rgba(251,113,133,0.28)"},
                ],
                "threshold": {"line": {"color": "#F8FAFC", "width": 2}, "value": 45},
            },
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#E2E8F0"},
        height=230,
        margin=dict(l=20, r=20, t=40, b=10),
    )
    return fig


def _twin_view(twin: CustomerTwin, hist: pd.DataFrame) -> None:
    left, center, right = st.columns([1.15, 1, 1.15])
    with left:
        st.markdown("##### Sales Twin")
        st.metric("Risk-adjusted LTV (90d)", f"${twin.ltv_90_adj:,.0f}", f"raw ${twin.ltv_90:,.0f}")
        st.metric("Next purchase", twin.next_purchase)
        st.metric("RFM", f"R{twin.r_score}  F{twin.f_score}  M{twin.m_score}")
        st.caption(f"{twin.frequency} orders · ${twin.monetary:,.0f} lifetime · {twin.product}")
        if not hist.empty:
            fig = go.Figure()
            fig.add_bar(x=hist["month"], y=hist["revenue"], marker_color="#2DD4BF", name="Orders")
            st.plotly_chart(_dark(fig).update_layout(title="This twin · buying history", height=220), use_container_width=True)

    with center:
        st.markdown("##### Twin core")
        st.markdown(
            f'<div class="pulse-ring"><div class="ring-val">{twin.health:.0f}</div>'
            f'<div class="ring-lbl">health</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="nba"><h3>{twin.action_title}</h3>'
            f"<p>{twin.action_play}</p><p><b>Offer:</b> {twin.offer}</p></div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{twin.customer_id} · {twin.name} · {twin.segment} · {twin.region} · {twin.rfm_segment}")

    with right:
        st.markdown("##### Churn Twin")
        st.plotly_chart(_gauge(twin.p_churn), use_container_width=True)
        st.metric("Primary reason", twin.churn_reason, None if not twin.at_risk else "AT RISK")
        st.caption(
            f"tickets {twin.support_tickets:.0f} · complaints {twin.complaints:.0f} · "
            f"email open {twin.email_open_rate:.0%} · recency {twin.recency_days}d"
        )


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    book = _ingest()
    models = _models(book)

    discount_pct = st.slider("Twin simulation · commercial discount", min_value=0, max_value=20, value=0, step=1, format="%d%%")
    discount = discount_pct / 100.0
    scored = simulate_discount(book.panel, models, discount) if discount > 0 else score_book(book.panel, models)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("At-risk twins", int(scored["at_risk"].sum()))
    k2.metric("At-risk LTV", f"${scored.loc[scored['at_risk'], 'ltv_90_adj'].sum():,.0f}")
    k3.metric("Save plays", int((scored["action_code"] == "SAVE_PREMIUM").sum()))
    k4.metric("Upsell plays", int((scored["action_code"] == "UPSELL_LOYALTY").sum()))
    k5.metric("Churn AUC", f"{models.metrics['churn_auc']:.2f}")

    st.markdown("#### Historical layer")
    _history_charts(book)

    st.markdown("#### Twin prediction layer")
    id_labels = {
        str(r.customer_id): f"{r.customer_id}  ·  {r.name}  ·  {r.action_title}  ·  {r.p_churn:.0%} churn"
        for r in scored.itertuples()
    }
    pick_id = st.selectbox(
        "Open a twin (sorted by expected value of action)",
        options=list(id_labels.keys()),
        format_func=lambda cid: id_labels[cid],
    )
    row = scored.loc[scored["customer_id"].astype(str) == pick_id].iloc[0]
    twin = twin_from_row(row)
    hist = customer_history(book.sales, twin.customer_id)
    _twin_view(twin, hist)

    pdf = twin_pdf(twin, discount=discount)
    st.download_button(
        "Export twin dossier (PDF)",
        data=pdf,
        file_name=f"twin_{twin.customer_id}.pdf",
        mime="application/pdf",
    )

    with st.expander("Model card · faculty / engineering"):
        st.write(models.metrics)
        if models.importances is not None:
            st.dataframe(models.importances.head(8), use_container_width=True, hide_index=True)
        st.dataframe(
            scored[
                [
                    "customer_id",
                    "name",
                    "ltv_90_adj",
                    "p_churn",
                    "health",
                    "action_title",
                    "churn_reason",
                    "next_purchase",
                ]
            ].head(25),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()
