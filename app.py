"""Keel Customer Twin — Streamlit 360. Historical CSVs in, future twin out."""

from __future__ import annotations

import hashlib

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.brain import score_book, simulate_discount
from src.data import DATA_DIR, TwinBook, write_demo
from src.history import customer_history, monthly_risk, monthly_sales
from src.models import TwinModels, train_twin_models
from src.pipeline import LAYER_CONTRACT, read_tabular, run_pipeline
from src.report import twin_pdf
from src.twin import CustomerTwin, twin_from_row
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


def _ingest() -> TwinBook:
    st.markdown(
        '<div class="hero"><h1>Customer Digital Twin</h1>'
        "<p>Forge-style data plane (DuckDB · raw vs clean · SQL) feeding an unchanged twin brain. "
        "Factory wall is OEE / Forge / PDM. This is the market wall.</p></div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    kinds = ["csv", "tsv", "xlsx"]
    up_c = c1.file_uploader("1 · customers (master)", type=kinds, key="c")
    up_s = c2.file_uploader("2 · sales (purchase sensors)", type=kinds, key="s")
    up_b = c3.file_uploader("3 · behavior (optional live health)", type=kinds, key="b")

    if not (DATA_DIR / "customers.csv").exists():
        write_demo()

    try:
        if up_c and up_s:
            customers = read_tabular(up_c)
            sales = read_tabular(up_s)
            behavior = read_tabular(up_b) if up_b else None
            source = "upload"
        elif up_c or up_s or up_b:
            st.error("Upload customers + sales. Behaviour is optional (inferred from last purchase).")
            st.stop()
        else:
            customers = pd.read_csv(DATA_DIR / "customers.csv")
            sales = pd.read_csv(DATA_DIR / "sales.csv")
            behavior = pd.read_csv(DATA_DIR / "behavior.csv")
            source = "demo book"
        pipe = run_pipeline(customers, sales, behavior)
    except (ValueError, OSError) as exc:
        st.error(str(exc))
        st.stop()

    book = pipe.book
    st.session_state["pipeline"] = pipe
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Raw master rows", f"{len(pipe.customers.raw):,}")
    m2.metric("Clean sales events", f"{len(pipe.sales.clean):,}")
    m3.metric("Twins (gold join)", f"{len(book.panel):,}")
    n_rej = len(pipe.customers.rejects) + len(pipe.sales.rejects) + len(pipe.behavior.rejects)
    m4.metric("Reject rows", f"{n_rej:,}")
    m5.metric("Behaviour", "inferred" if pipe.behavior_source == "inferred_from_sales" else "uploaded")
    st.caption(f"Source: {source} · join `customer_id` · unmatched {book.dropped_ids:,} · {pipe.gold_note}")

    with st.expander("Data plane · 8 layers · raw vs clean · DuckDB SQL (Forge v2 slice)", expanded=False):
        st.write("Contract: " + " → ".join(LAYER_CONTRACT))
        st.dataframe(pipe.layer_rows, use_container_width=True, hide_index=True)
        t1, t2, t3, t4 = st.tabs(["Raw vs clean", "Rejects", "SQL lab", "Gold panel"])
        with t1:
            feed = st.selectbox("Feed", ["customers", "sales", "behavior"])
            left, right = st.columns(2)
            raw_map = {"customers": pipe.customers.raw, "sales": pipe.sales.raw, "behavior": pipe.behavior.raw}
            clean_map = {"customers": pipe.customers.clean, "sales": pipe.sales.clean, "behavior": pipe.behavior.clean}
            left.caption("RAW (untouched)")
            left.dataframe(raw_map[feed].head(40), use_container_width=True)
            right.caption("CLEAN (rules applied)")
            right.dataframe(clean_map[feed].head(40), use_container_width=True)
        with t2:
            st.caption("Customers rejects")
            st.dataframe(pipe.customers.rejects.head(30), use_container_width=True)
            st.caption("Sales rejects")
            st.dataframe(pipe.sales.rejects.head(30), use_container_width=True)
            st.caption("Behaviour rejects")
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
                except Exception as exc:  # show analyst-facing SQL errors
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
