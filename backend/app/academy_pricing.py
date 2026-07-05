"""A5 — academy entrance-aptitude tiered discount + enrolment pricing.

FOUNDER-LOCKED (C.2 discipline — do NOT reinterpret):
  discount tiers, INCLUSIVE-LOWER boundaries:
    ≥95 → 20% | 85–<95 → 15% | 75–<85 → 10% | <75 → 0%
  <75 is FULL PRICE, NOT a gate (decision 5): resolve returns 0, enrolment still
  proceeds — the test is a PRICING LEVER, never a block.

Clean boundary property (worth stating): the aptitude score is the SAME canonical
percentage stamped as enrollment.aptitude_score = correct/60 × 100. The tier
boundaries fall on EXACT integer correct-counts — 60×0.95 = 57, 60×0.85 = 51,
60×0.75 = 45 (all integers) — so there is NO rounding ambiguity at any boundary:
57/60 = 95.0 → 20, 56/60 = 93.33… → 15, etc.

final_fee is the PRE-TAX discounted COURSE fee. GST/TDS stay INERT (standing
principle — inert until CA confirms). The fee is READ off course.fee (per-course
configurable, A1 seed) — NEVER hardcoded. Discount stamps as a PRICE (decision 4):
only discount_percent + final_fee on the enrollment; no coupon entity.
"""
from __future__ import annotations


def resolve_discount_percent(percentage) -> int:
    """Pure, no I/O. Maps an aptitude percentage to the founder-locked discount %
    (inclusive-lower boundaries). <75 → 0 (full price, NOT a block)."""
    p = float(percentage)
    if p >= 95:
        return 20
    if p >= 85:
        return 15
    if p >= 75:
        return 10
    return 0


def compute_final_fee(course_fee, discount_percent: int) -> float:
    """PRE-TAX discounted course fee = course_fee × (100 − discount)/100, rounded
    to 2 decimals via the SAME convention as the B.9 invoice fee (round(float, 2)).
    NO GST/TDS (inert). Reads the fee that is PASSED IN (course.fee), never a
    hardcoded default."""
    return round(float(course_fee) * (100 - discount_percent) / 100, 2)
