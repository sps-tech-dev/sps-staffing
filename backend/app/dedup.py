"""Duplicate detection (B.3) — the FUZZY layer.

EXACT duplicate detection is NOT here and is unchanged: it is enforced by the
blind-index uniques UNIQUE(tenant_id, phone_bidx) / UNIQUE(tenant_id, pan_bidx)
on staffing.candidates — an IntegrityError surfaced as 409 at the create sites.

This module finds candidates the exact check let through: same-ish person with a
DIFFERENT (or missing) phone/PAN. It operates ONLY on non-encrypted fields —
full_name (plaintext), skills, resume_text — and NEVER decrypts phone/pan.

Guard against common-name false positives: a pg_trgm name similarity above the
threshold alone NEVER flags — it must be corroborated by a SECOND signal
(case-insensitive skill overlap, or resume-text trigram similarity when the
caller has text). Model is create-then-flag: callers create the candidate, then
insert a pending staffing.candidate_dup_reviews row for the best hit.

pg_trgm lives in the `public` schema (migration 0022); similarity() is called
schema-qualified as public.similarity() so resolution never depends on the
connection's search_path.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings


@dataclass(frozen=True)
class FuzzyHit:
    candidate_id: uuid.UUID
    score: float
    signal: str  # 'skills' | 'resume'


def fuzzy_scan(db: Session, *, tenant_id, exclude_candidate_id, full_name: str,
               skills: list[str] | None = None,
               resume_text: str | None = None) -> FuzzyHit | None:
    """Best fuzzy duplicate for an incoming candidate within the tenant, or None.

    Name similarity >= settings.dedup_name_similarity AND (skill overlap OR
    resume-text similarity >= settings.dedup_resume_similarity). Excludes the
    just-created candidate itself and soft-deleted rows. Returns the single best
    hit by name score (one review per intake keeps the queue readable).
    """
    if not full_name:
        return None
    skills_lower = [s.lower() for s in (skills or []) if s and s.strip()]
    resume_probe = (resume_text or "")[:4000]

    row = db.execute(text("""
        SELECT id,
               public.similarity(full_name, :name) AS name_score,
               CASE
                 WHEN :has_skills AND skills IS NOT NULL AND EXISTS (
                      SELECT 1 FROM unnest(skills) s
                      WHERE lower(s) = ANY(CAST(:skills_lower AS text[]))
                 ) THEN 'skills'
                 WHEN :has_resume AND resume_text IS NOT NULL AND
                      public.similarity(left(resume_text, 4000), :resume_probe)
                        >= :resume_threshold
                 THEN 'resume'
               END AS signal
        FROM staffing.candidates
        WHERE tenant_id = :tid
          AND id <> :self_id
          AND deleted_at IS NULL
          AND public.similarity(full_name, :name) >= :name_threshold
          AND (
                (:has_skills AND skills IS NOT NULL AND EXISTS (
                     SELECT 1 FROM unnest(skills) s
                     WHERE lower(s) = ANY(CAST(:skills_lower AS text[]))
                ))
             OR (:has_resume AND resume_text IS NOT NULL AND
                 public.similarity(left(resume_text, 4000), :resume_probe)
                   >= :resume_threshold)
          )
        ORDER BY name_score DESC
        LIMIT 1
    """), {
        "tid": str(tenant_id), "self_id": str(exclude_candidate_id), "name": full_name,
        "name_threshold": settings.dedup_name_similarity,
        "resume_threshold": settings.dedup_resume_similarity,
        "has_skills": bool(skills_lower), "skills_lower": skills_lower,
        "has_resume": bool(resume_probe), "resume_probe": resume_probe,
    }).first()

    if row is None:
        return None
    return FuzzyHit(candidate_id=row.id, score=float(row.name_score), signal=row.signal or "skills")


def flag_if_fuzzy_dup(db: Session, *, tenant_id, candidate, skills=None,
                      resume_text=None, source: str) -> None:
    """create-then-flag: after a candidate is created (flushed, id assigned) and the
    exact check has passed, insert ONE pending dup_reviews row for the best fuzzy
    hit. Runs inside the caller's transaction. Non-PII snapshot only (no phone/pan)."""
    from .models_staffing import CandidateDupReview  # local import avoids a cycle

    hit = fuzzy_scan(db, tenant_id=tenant_id, exclude_candidate_id=candidate.id,
                     full_name=candidate.full_name, skills=skills, resume_text=resume_text)
    if hit is None:
        return
    db.add(CandidateDupReview(
        tenant_id=uuid.UUID(str(tenant_id)), business_unit_id="STAFFING",
        candidate_id=candidate.id, matched_candidate_id=hit.candidate_id,
        match_type="fuzzy", score=hit.score,
        incoming_payload={"full_name": candidate.full_name, "skills": skills or [],
                          "signal": hit.signal, "source": source},
    ))
