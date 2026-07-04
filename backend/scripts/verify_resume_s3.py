"""One-off B.1 verification against the REAL dev bucket (what moto can't prove).

Runs in the BACKEND task definition (command override) so it uses the task role
(S3 perms), the injected S3_BUCKET env (the C5 config fix under test) and the
least-privilege `sps_app` DB creds — the exact runtime path production traffic takes.

Flow: probe candidate row → presign PUT → real HTTP PUT (urllib, no SDK creds on the
"client" side) → head/size check → server-side download + text extraction → persist →
presign GET → real HTTP GET (bytes match) → erasure-style delete (object + nulls) →
cleanup probe row. Exits non-zero on any failure. Self-cleaning; safe to re-run.
"""
from __future__ import annotations

import sys
import urllib.request

from sqlalchemy import text as sql

from app import resume_parse, storage
from app.config import settings
from app.db import get_sessionmaker

PROBE_NAME = "[B.1 S3 verification probe]"


def _mini_pdf(text_line: str = "B1 Probe Resume Text Extraction OK") -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text_line}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
            b"startxref\n" + str(xref).encode() + b"\n%%EOF\n")
    return bytes(out)


def _http(method: str, url: str, data: bytes | None = None, content_type: str | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, method=method)
    if content_type:
        req.add_header("Content-Type", content_type)
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert 200 <= resp.status < 300, f"{method} {resp.status}"
        return resp.read()


def main() -> int:
    print(f"bucket = {settings.storage_bucket} (from S3_BUCKET — C5 fix under test)")
    db = get_sessionmaker()()
    cid = key = None
    ok = False
    try:
        tid = db.execute(sql("SELECT id FROM shared.tenants WHERE code='SPS001'")).scalar_one()
        cid = db.execute(sql(
            "INSERT INTO staffing.candidates (tenant_id, full_name) "
            "VALUES (:t, :n) RETURNING id"), {"t": tid, "n": PROBE_NAME}).scalar_one()
        db.commit()
        print(f"1. probe candidate {cid} created (as sps_app)")

        data = _mini_pdf()
        key = storage.build_candidate_resume_key(tid, cid, "pdf")
        put_url = storage.presign_put(key, "application/pdf")
        _http("PUT", put_url, data=data, content_type="application/pdf")
        print("2. presigned PUT to the real bucket ✅")

        head = storage.head_object(key)
        assert head and int(head["ContentLength"]) == len(data), "head/size mismatch"
        print(f"3. head_object size={head['ContentLength']} ✅")

        extracted = resume_parse.extract_text(storage.get_object_bytes(key), "application/pdf")
        assert "Probe Resume" in extracted, f"extraction failed: {extracted[:80]!r}"
        db.execute(sql(
            "UPDATE staffing.candidates SET resume_s3_key=:k, resume_text=:x, "
            "resume_uploaded_at=now() WHERE id=:i"), {"k": key, "x": extracted, "i": cid})
        db.commit()
        print("4. server-side download + text extraction + persist (0020 columns) ✅")

        got = _http("GET", storage.presign_get(key))
        assert got == data, "presigned GET bytes mismatch"
        print("5. presigned GET round-trip ✅")

        storage.delete_object(key)
        assert storage.head_object(key) is None, "object survived delete"
        db.execute(sql(
            "UPDATE staffing.candidates SET resume_s3_key=NULL, resume_text=NULL, "
            "resume_uploaded_at=NULL WHERE id=:i"), {"i": cid})
        db.commit()
        key = None
        print("6. erasure-style delete: object gone + columns nulled ✅")
        ok = True
    finally:
        if key:
            try:
                storage.delete_object(key)
            except Exception as e:  # noqa: BLE001
                print(f"cleanup: object delete failed: {e}")
        if cid:
            db.execute(sql("DELETE FROM staffing.candidates WHERE id=:i"), {"i": cid})
            db.commit()
            print("7. probe candidate cleaned up")
        db.close()
    print("B.1 REAL-S3 VERIFICATION: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
