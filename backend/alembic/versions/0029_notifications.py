"""0029 notification service scaffolding — templates + delivery ledger (B.10)

Revision ID: 0029_notifications
Revises: 0028_placements
Create Date: 2026-07-04

TRANSPORT DECISION (settled): durable enqueue-TABLE + one-off runner (the B.9
pattern) — shared.notifications IS the queue, the delivery-status record, the
idempotency ledger and the audit trail in one store. No Redis queue (a second
store to reconcile); worker/Redis is a future scale-up behind the same interface.

These are OPERATIONAL tables, deliberately NOT append-only (status/attempts are
UPDATE-in-place — unlike audit_logs/consents/candidate_timeline) → normal DML for
sps_app, NOT in the bootstrap REVOKE list.

Seed: three PROVISIONAL operational templates (assessment_result,
interview_reminder, invoice_dunning). Operational copy only — legal/consent
notices stay STOP-3 and are NOT seeded here. Template channel_type records the
INTENDED real channel (email); in dev the NOTIFY_CHANNEL_OVERRIDE=console setting
routes deliveries to the ConsoleChannel sink.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = '0029_notifications'
down_revision = '0028_placements'
branch_labels = None
depends_on = None

TEMPLATES = [
    ("assessment_result", "email", "Your SPS assessment result",
     "Hi {candidate_name},\n\nYour aptitude assessment for {job_title} has been "
     "evaluated. Result: {result}.\n\nSPS Technosoft Staffing\n"
     "[PROVISIONAL operational copy — refine before real sends]"),
    ("interview_reminder", "email", "Interview scheduled: {job_title}",
     "Hi {candidate_name},\n\nYour interview for {job_title} is scheduled at "
     "{scheduled_at} ({mode}). A calendar invite (.ics) will be attached when "
     "email delivery goes live.\n\nSPS Technosoft Staffing\n"
     "[PROVISIONAL operational copy — refine before real sends]"),
    ("invoice_dunning", "email", "Payment reminder: invoice {invoice_number}",
     "Dear {client_name},\n\nInvoice {invoice_number} (total {total_amount}) is "
     "overdue by {age_days} days. Please arrange payment.\n\nSPS Technosoft\n"
     "[PROVISIONAL operational copy — refine before real sends]"),
]


def upgrade() -> None:
    op.create_table(
        'notification_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('code', sa.Text(), nullable=False, unique=True),
        sa.Column('channel_type', sa.Text(), nullable=False),
        sa.Column('subject', sa.Text(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        schema='shared',
    )
    op.create_table(
        'notifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False),
        sa.Column('business_unit_id', sa.Text(), nullable=False),
        sa.Column('template_code', sa.Text(), nullable=False),
        sa.Column('channel_type', sa.Text(), nullable=False),
        sa.Column('recipient', sa.Text(), nullable=False),
        sa.Column('vars', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('rendered_subject', sa.Text(), nullable=True),
        sa.Column('rendered_body', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','sent','failed','skipped')",
                           name='ck_notifications_status'),
        sa.UniqueConstraint('idempotency_key', name='uq_notifications_idempotency_key'),
        schema='shared',
    )
    op.create_index('ix_notifications_status_created', 'notifications',
                    ['status', 'created_at'], schema='shared')
    op.create_index('ix_notifications_tenant', 'notifications', ['tenant_id'], schema='shared')

    for code, ch, subject, body in TEMPLATES:
        op.execute(sa.text(
            "INSERT INTO shared.notification_templates (code, channel_type, subject, body) "
            "VALUES (:c, :ch, :s, :b)").bindparams(c=code, ch=ch, s=subject, b=body))


def downgrade() -> None:
    op.drop_index('ix_notifications_tenant', table_name='notifications', schema='shared')
    op.drop_index('ix_notifications_status_created', table_name='notifications', schema='shared')
    op.drop_table('notifications', schema='shared')
    op.drop_table('notification_templates', schema='shared')
