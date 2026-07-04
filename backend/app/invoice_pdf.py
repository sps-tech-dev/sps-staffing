"""Invoice PDF rendering (B.9) — ReportLab, free, no template service.

Layout honors the Part 0-FEE honesty rule: the placement fee is ONE LINE ITEM
(annual CTC × resolved %); GST and TDS appear as their own lines marked
"pending CA confirmation (C.3)" with 0.00 — the pre-tax total is NEVER presented
as a final taxed amount. Invoice numbering is PROVISIONAL (format is a C.3
input) and clearly marked as such on the document.
"""
from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def provisional_number(invoice_id) -> str:
    """PROVISIONAL sequence — the statutory numbering format awaits C.3."""
    return f"PROV-{str(invoice_id).replace('-', '')[:10].upper()}"


def _inr(x) -> str:
    return f"INR {float(x):,.2f}" if x is not None else "—"


def build_invoice_pdf(*, invoice, client_name: str, candidate_name: str,
                      job_title: str | None, joined_on=None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 25 * mm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "SPS Technosoft — Placement Invoice")
    y -= 7 * mm
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, f"Invoice no: {provisional_number(invoice.id)}  "
                             "(PROVISIONAL — statutory numbering format pending C.3)")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Status: {invoice.status}"
                             + ("   [REPLACEMENT — fee exempt]" if invoice.is_replacement else "")
                             + ("   [CREDIT NOTE]" if invoice.credit_note_of else ""))
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "Placement details")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    for label, val in (("Client", client_name), ("Candidate", candidate_name),
                       ("Position", job_title or "—"),
                       ("Joined on", joined_on.isoformat() if joined_on else "—"),
                       ("Annual CTC (base)", _inr(invoice.base_amount))):
        c.drawString(22 * mm, y, f"{label}: {val}")
        y -= 5.5 * mm
    y -= 6 * mm

    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "Charges")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    fee_pct = float(invoice.fee_percent)
    c.drawString(22 * mm, y,
                 f"Placement service fee ({fee_pct:g}% of annual CTC)")
    c.drawRightString(w - 22 * mm, y, _inr(invoice.fee_amount))
    y -= 6 * mm
    # GST/TDS: present-but-pending lines — NEVER folded into one number (Part 0-FEE #4)
    gst = invoice.gst_amount if invoice.gst_percent is not None else None
    tds = invoice.tds_amount if invoice.tds_percent is not None else None
    c.drawString(22 * mm, y, "GST — pending CA confirmation (C.3)")
    c.drawRightString(w - 22 * mm, y, _inr(gst) if gst is not None else "0.00 (pending)")
    y -= 6 * mm
    c.drawString(22 * mm, y, "TDS — pending CA confirmation (C.3)")
    c.drawRightString(w - 22 * mm, y, _inr(tds) if tds is not None else "0.00 (pending)")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(22 * mm, y, "Total (pre-tax — taxes pending C.3)")
    c.drawRightString(w - 22 * mm, y, _inr(invoice.total_amount))

    y -= 15 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(20 * mm, y, "This document is generated for internal/dev use. GST/TDS lines are "
                             "intentionally pending until CA-confirmed rules (PENDING B5 / C.3).")
    c.showPage()
    c.save()
    return buf.getvalue()
