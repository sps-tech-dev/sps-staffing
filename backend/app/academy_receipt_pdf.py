"""A6 — academy enrolment payment receipt PDF. Reuses the exact ReportLab+S3 seam
as invoice_pdf (canvas → bytes → storage.put_object → presign_get); receipt content
only. PROVISIONAL — GST/TDS inert (final_fee is pre-tax), statutory numbering pending.
"""
from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def provisional_receipt_number(payment_id) -> str:
    return f"ACAD-RCPT-{str(payment_id)[:8].upper()} (PROVISIONAL)"


def build_receipt_pdf(*, payment, enrollment, course_title: str, student_name: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 25 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "SPS Technosoft Academy — Payment Receipt")
    y -= 7 * mm
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, f"Receipt no: {provisional_receipt_number(payment.id)}")
    y -= 5 * mm
    paid = payment.paid_at.date().isoformat() if payment.paid_at else "—"
    c.drawString(20 * mm, y, f"Paid on: {paid}    Status: {payment.status}")
    y -= 10 * mm
    c.setFont("Helvetica", 11)
    for line in (
        f"Student: {student_name}",
        f"Course: {course_title}",
        f"Aptitude score: {enrollment.aptitude_score}%   Discount: {enrollment.discount_percent}%",
        f"Amount paid: {payment.amount} {payment.currency}  (pre-tax; GST/TDS pending — C.3)",
        f"Provider: {payment.provider}   Ref: {payment.provider_ref or '—'}",
    ):
        c.drawString(20 * mm, y, line)
        y -= 7 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(20 * mm, 20 * mm, "PROVISIONAL receipt — statutory numbering/tax format pending (C.3).")
    c.showPage()
    c.save()
    return buf.getvalue()
