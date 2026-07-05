"""A3 — academy-student auth dependency (SEPARATE from staffing's
get_current_context, never a branch of it). A staff endpoint structurally cannot
accept a student token because it never calls this resolver; this resolver
structurally cannot accept a staffing token because it (1) reads a DISTINCT
cookie, (2) decodes with a DISTINCT secret, and (3) requires kind='academy_student'.
Any one of the three failing → 401. Containment is cryptographic + claim-based +
cookie-based, in that order of strength.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .features import is_enabled
from .models_academy import Student
from .security import decode_academy_token

ACADEMY_COOKIE = "academy_access_token"   # DISTINCT from staffing's 'access_token'


@dataclass
class StudentContext:
    student_id: uuid.UUID          # academy.students.id (the auth subject)
    tenant_id: str
    email: str | None
    college_student_id: str | None


def get_current_student(request: Request, db: Session = Depends(get_db)) -> StudentContext:
    if not is_enabled("academy"):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Not found"})
    token = request.cookies.get(ACADEMY_COOKIE)
    payload = decode_academy_token(token) if token else None
    # kind check is defense-in-depth on top of the distinct secret + type + cookie
    if not payload or payload.get("kind") != "academy_student":
        raise HTTPException(status_code=401,
                            detail={"code": "UNAUTHENTICATED", "message": "Student authentication required"})
    st = db.execute(select(Student).where(
        Student.id == uuid.UUID(str(payload["sub"])),
        Student.tenant_id == uuid.UUID(str(payload["tenant_id"])),
        Student.deleted_at.is_(None))).scalar_one_or_none()
    if st is None:
        raise HTTPException(status_code=401,
                            detail={"code": "UNAUTHENTICATED", "message": "Student session no longer valid"})
    return StudentContext(student_id=st.id, tenant_id=str(st.tenant_id), email=st.email,
                          college_student_id=st.student_id)
