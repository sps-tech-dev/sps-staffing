"""0024 pipeline hardening — full Part-5 stage vocabulary + optimistic lock + RTR (B.5)

Revision ID: 0024_pipeline_stages
Revises: 0023_search_doc_trigger
Create Date: 2026-07-04

Expand/contract over EXISTING data (single migration — dev is ~small and the
mapping is deterministic; STOP-1 approved):
  1. applications: + version (optimistic lock), hold_reason, drop_reason,
     hold_prior_stage (reopen target), rtr_consent_at/rtr_consent_by (the
     submit-gate representation, ratified at STOP-1).
  2. shared.consents purpose CHECK widened to include 'rtr' (the DPDP trail row
     appended by POST /applications/{id}/rtr).
  3. stage vocabulary: DROP old CHECK → CASE-map every old value to the new
     Part-5 set → ADD the new CHECK. Legacy 'rejected' rows become 'dropped'
     with a tagged drop_reason.

PROD NOTE: on a populated table the CASE UPDATE is a full-table rewrite — batch
it and VALIDATE the new CHECK separately (ADD CONSTRAINT ... NOT VALID; VALIDATE
CONSTRAINT). Dev is ~empty so a single pass is safe.

Downgrade is best-effort reversible: reverse-maps new→old (lossy where the new
vocabulary is finer: aptitude_*/internal_* collapse back to screened/assessed,
client_round_* to interview, joined/guarantee/invoiced/paid to placed,
withdrawn/dropped to rejected), restores the old CHECK, drops the new columns,
and restores the consents CHECK (deleting any 'rtr' rows first — dev-only
concession, documented).
"""
from alembic import op
import sqlalchemy as sa

revision = '0024_pipeline_stages'
down_revision = '0023_search_doc_trigger'
branch_labels = None
depends_on = None

S = 'staffing'

NEW_STAGES = (
    "applied", "screening", "aptitude_test", "aptitude_passed", "aptitude_failed",
    "internal_interview", "internal_passed", "rtr_pending", "submitted_to_client",
    "client_round_1", "client_round_2", "client_round_3", "offer", "offer_accepted",
    "joined", "guarantee", "invoiced", "paid", "withdrawn", "dropped", "on_hold",
)
OLD_STAGES = ("sourced", "screened", "assessed", "submitted",
              "interview", "offer", "placed", "rejected", "on_hold")

_NEW_SQL = ", ".join(f"'{s}'" for s in NEW_STAGES)
_OLD_SQL = ", ".join(f"'{s}'" for s in OLD_STAGES)

# STOP-1-approved mapping (Part 0c)
FORWARD = {
    "sourced": "applied", "screened": "screening", "assessed": "aptitude_passed",
    "submitted": "submitted_to_client", "interview": "client_round_1",
    "offer": "offer", "placed": "joined", "rejected": "dropped", "on_hold": "on_hold",
}
# best-effort reverse (lossy — see docstring)
REVERSE = {
    "applied": "sourced", "screening": "screened",
    "aptitude_test": "screened", "aptitude_passed": "assessed", "aptitude_failed": "screened",
    "internal_interview": "assessed", "internal_passed": "assessed", "rtr_pending": "assessed",
    "submitted_to_client": "submitted",
    "client_round_1": "interview", "client_round_2": "interview", "client_round_3": "interview",
    "offer": "offer", "offer_accepted": "offer",
    "joined": "placed", "guarantee": "placed", "invoiced": "placed", "paid": "placed",
    "withdrawn": "rejected", "dropped": "rejected", "on_hold": "on_hold",
}


def _case(mapping: dict) -> str:
    whens = " ".join(f"WHEN '{o}' THEN '{n}'" for o, n in mapping.items())
    return f"CASE stage {whens} ELSE stage END"


def upgrade() -> None:
    # 1. new columns
    op.add_column('applications', sa.Column('version', sa.Integer(), nullable=False,
                                            server_default=sa.text('1')), schema=S)
    op.add_column('applications', sa.Column('hold_reason', sa.Text(), nullable=True), schema=S)
    op.add_column('applications', sa.Column('drop_reason', sa.Text(), nullable=True), schema=S)
    op.add_column('applications', sa.Column('hold_prior_stage', sa.Text(), nullable=True), schema=S)
    op.add_column('applications', sa.Column('rtr_consent_at', sa.DateTime(timezone=True),
                                            nullable=True), schema=S)
    op.add_column('applications', sa.Column('rtr_consent_by', sa.UUID(), nullable=True), schema=S)

    # 2. consents purpose CHECK += 'rtr'
    op.drop_constraint('ck_consents_purpose', 'consents', schema='shared', type_='check')
    op.create_check_constraint('ck_consents_purpose', 'consents',
                               "purpose IN ('data_processing','marketing','cookies','rtr')",
                               schema='shared')

    # 3. stage vocabulary: drop CHECK → data-migrate → new CHECK
    op.drop_constraint('ck_applications_stage', 'applications', schema=S, type_='check')
    op.execute(f"UPDATE {S}.applications SET drop_reason = 'legacy: rejected (pre-B.5 vocabulary)' "
               f"WHERE stage = 'rejected'")
    op.execute(f"UPDATE {S}.applications SET stage = {_case(FORWARD)}")
    op.create_check_constraint('ck_applications_stage', 'applications',
                               f"stage IN ({_NEW_SQL})", schema=S)


def downgrade() -> None:
    op.drop_constraint('ck_applications_stage', 'applications', schema=S, type_='check')
    op.execute(f"UPDATE {S}.applications SET stage = {_case(REVERSE)}")
    op.create_check_constraint('ck_applications_stage', 'applications',
                               f"stage IN ({_OLD_SQL})", schema=S)

    # consents CHECK back (dev-only concession: purge 'rtr' rows so the CHECK holds)
    op.execute("DELETE FROM shared.consents WHERE purpose = 'rtr'")
    op.drop_constraint('ck_consents_purpose', 'consents', schema='shared', type_='check')
    op.create_check_constraint('ck_consents_purpose', 'consents',
                               "purpose IN ('data_processing','marketing','cookies')",
                               schema='shared')

    op.drop_column('applications', 'rtr_consent_by', schema=S)
    op.drop_column('applications', 'rtr_consent_at', schema=S)
    op.drop_column('applications', 'hold_prior_stage', schema=S)
    op.drop_column('applications', 'drop_reason', schema=S)
    op.drop_column('applications', 'hold_reason', schema=S)
    op.drop_column('applications', 'version', schema=S)
