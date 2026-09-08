"""Enterprise twin dossier PDF."""

from __future__ import annotations

from io import BytesIO

from fpdf import FPDF

from src.twin import CustomerTwin


class TwinPDF(FPDF):
    def header(self) -> None:
        self.set_fill_color(7, 11, 20)
        self.rect(0, 0, 210, 18, "F")
        self.set_text_color(45, 212, 191)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 12, "  KEEL  ·  Customer Digital Twin dossier", align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(148, 163, 184)
        self.cell(
            0,
            8,
            "OEE -> Forge -> PDM -> Customer Twin   |   Factory wall in. Market wall out.",
            align="C",
        )


def twin_pdf(twin: CustomerTwin, discount: float = 0.0) -> bytes:
    pdf = TwinPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_text_color(226, 232, 240)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, twin.name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(
        0,
        6,
        f"{twin.customer_id}  |  {twin.segment}  |  {twin.region}  |  {twin.product}  |  {twin.rfm_segment}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    def kv(key: str, value: str) -> None:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(45, 212, 191)
        pdf.cell(52, 7, key)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(226, 232, 240)
        pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")

    kv("Sales LTV 90d (risk-adj)", f"${twin.ltv_90_adj:,.0f}")
    kv("Raw LTV 90d", f"${twin.ltv_90:,.0f}")
    kv("RFM", f"R{twin.r_score} F{twin.f_score} M{twin.m_score}  ({twin.sales_strength:.0%} strength)")
    kv("Next purchase", twin.next_purchase)
    kv("Lifetime monetary", f"${twin.monetary:,.2f} across {twin.frequency} orders")
    pdf.ln(2)
    kv("Churn probability", f"{twin.p_churn:.0%}   {twin.band}")
    kv("Health", f"{twin.health:.0f} / 100")
    kv("Health why", twin.health_why()[:220])
    kv("Expected value of action", twin.ev_line())
    kv("Primary reason", twin.churn_reason)
    kv("Live sensors", f"tickets {twin.support_tickets:.0f}  complaints {twin.complaints:.0f}  open {twin.email_open_rate:.0%}")
    pdf.ln(3)
    kv("NEXT BEST ACTION", twin.action_title)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(226, 232, 240)
    pdf.multi_cell(0, 6, twin.action_play)
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(0, 6, f"Offer: {twin.offer}")
    if discount:
        pdf.ln(2)
        pdf.set_text_color(45, 212, 191)
        pdf.multi_cell(0, 6, f"Simulation: {discount:.0%} commercial discount applied to this twin run.")
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.multi_cell(
        0,
        5,
        "Join: customers.csv x sales.csv x behavior.csv on customer_id. "
        "Sales Twin = RFM + HGB LTV/next-buy. Churn Twin = behavioral decay + calibrated HGB. "
        "LTV is risk-adjusted on the same clock.",
    )
    buf = BytesIO()
    pdf.output(buf)
    return bytes(buf.getvalue())
