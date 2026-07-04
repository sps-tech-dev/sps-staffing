"""0020 candidate resume — extracted text + upload timestamp (B.1)

Revision ID: 0020_candidate_resume
Revises: 0019_client_roles_owner
Create Date: 2026-07-04

Resume upload support (master plan B.1). `resume_s3_key` already exists (0004);
this adds the server-side extracted text (feeds search B.4 later) and the upload
timestamp. Additive + reversible; both columns NULL for existing rows.

resume_text contains PII — the erasure anonymize path nulls it together with
resume_s3_key (and deletes the S3 object).
"""
from alembic import op
import sqlalchemy as sa

revision = '0020_candidate_resume'
down_revision = '0019_client_roles_owner'
branch_labels = None
depends_on = None

S = 'staffing'


def upgrade() -> None:
    op.add_column('candidates', sa.Column('resume_text', sa.Text(), nullable=True), schema=S)
    op.add_column('candidates',
                  sa.Column('resume_uploaded_at', sa.DateTime(timezone=True), nullable=True),
                  schema=S)


def downgrade() -> None:
    op.drop_column('candidates', 'resume_uploaded_at', schema=S)
    op.drop_column('candidates', 'resume_text', schema=S)
