"""0023 candidate search — search_doc trigger + backfill (B.4)

Revision ID: 0023_search_doc_trigger
Revises: 0022_dup_reviews_pg_trgm
Create Date: 2026-07-04

search_doc (tsvector, exists since 0004) becomes MAINTAINED: a BEFORE INSERT OR
UPDATE trigger recomputes it from NON-encrypted fields only — full_name (weight A)
+ skills (B) + resume_text (C). It NEVER touches email/phone/pan (*_enc) — the
index must carry no PII beyond the already-plaintext name.

Erasure interplay (the rule that must hold): if NEW.deleted_at IS NOT NULL the
trigger FORCES search_doc := NULL instead of recomputing — so the erasure
anonymize UPDATE (which sets deleted_at) can never re-index a scrubbed row, and
the disable-on-request soft-delete de-indexes immediately.

tsvector config = 'simple': the corpus is proper names + tech skill tokens +
multilingual content; English stemming adds variance without recall benefit.

NOTE: the GIN index on search_doc ALREADY EXISTS (ix_candidates_search, 0004) —
deliberately NOT re-created here. (Prod note kept for symmetry: GIN builds on a
populated table should be CONCURRENTLY, outside a txn.)

Backfill: a no-op UPDATE fires the trigger for every row (active rows computed,
soft-deleted rows nulled). Dev is ~empty; trivial.

Downgrade drops trigger + function; the column and 0004 index remain.
"""
from alembic import op

revision = '0023_search_doc_trigger'
down_revision = '0022_dup_reviews_pg_trgm'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION staffing.candidates_search_doc_refresh()
        RETURNS trigger AS $$
        BEGIN
          IF NEW.deleted_at IS NOT NULL THEN
            NEW.search_doc := NULL;
          ELSE
            NEW.search_doc :=
              setweight(to_tsvector('simple', coalesce(NEW.full_name, '')), 'A') ||
              setweight(to_tsvector('simple',
                        coalesce(array_to_string(NEW.skills, ' '), '')), 'B') ||
              setweight(to_tsvector('simple',
                        coalesce(left(NEW.resume_text, 100000), '')), 'C');
          END IF;
          RETURN NEW;
        END
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_candidates_search_doc
        BEFORE INSERT OR UPDATE ON staffing.candidates
        FOR EACH ROW EXECUTE FUNCTION staffing.candidates_search_doc_refresh()
    """)
    # backfill: no-op UPDATE fires the trigger on every existing row
    op.execute("UPDATE staffing.candidates SET search_doc = search_doc")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_candidates_search_doc ON staffing.candidates")
    op.execute("DROP FUNCTION IF EXISTS staffing.candidates_search_doc_refresh()")
