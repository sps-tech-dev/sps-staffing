"""0003 seed owner tenant SPS001

Revision ID: 0003_seed_owner_tenant
Revises: 0002_shared_spine
Create Date: 2026-06-26

Idempotent DATA migration (Part 2 Definition of Done): seeds the owner tenant
SPS001, its three business units, an internal plan + active subscription, and a
PASSWORD-LESS founder user (status='invited', sentinel hash). FKs are resolved
by natural-key lookup (never hardcoded UUIDs). Every INSERT uses ON CONFLICT
DO NOTHING so re-running creates no duplicates.

NO CREDENTIALS IN THIS FILE: the founder cannot log in until a password is set
out-of-band via scripts/set-founder-password.sh (see DECISIONS).
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_seed_owner_tenant"
down_revision = "0002_shared_spine"
branch_labels = None
depends_on = None

# Sentinel password hash: NOT a real argon2 hash and NOT a hash of any known
# password — argon2 verify() rejects it, so the account is unusable until reset.
SENTINEL_PW = "!"
FOUNDER_EMAIL = "sandeep@spstechnosoft.com"


def upgrade() -> None:
    # 1) Owner tenant
    op.execute(
        """
        INSERT INTO shared.tenants (code, slug, name)
        VALUES ('SPS001', 'sps', 'SPS Technosoft')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # 2) Three business units under SPS001 (tenant id resolved by code)
    op.execute(
        """
        INSERT INTO shared.business_units (tenant_id, code, name, features)
        SELECT t.id, v.code, v.name, '{}'::jsonb
        FROM shared.tenants t
        CROSS JOIN (VALUES
            ('STAFFING',   'Staffing & Recruitment'),
            ('ACADEMY',    'Training & Academy'),
            ('CONSULTING', 'IT Services & Consulting')
        ) AS v(code, name)
        WHERE t.code = 'SPS001'
        ON CONFLICT (tenant_id, code) DO NOTHING;
        """
    )

    # 3) Internal plan: all verticals + features on, unlimited (-1) limits
    op.execute(
        """
        -- JSONB built via jsonb_build_object/array to avoid colon-prefixed
        -- tokens that SQLAlchemy text() would treat as bind parameters.
        INSERT INTO shared.plans (code, price_inr, period, limits, features)
        VALUES (
            'internal', 0, 'internal',
            jsonb_build_object('jobs', -1, 'users', -1, 'ai_calls', -1),
            jsonb_build_object(
                'verticals', jsonb_build_array('STAFFING', 'ACADEMY', 'CONSULTING'),
                'all_features', true
            )
        )
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # 4) Active subscription: SPS001 -> internal plan
    op.execute(
        """
        INSERT INTO shared.tenant_subscriptions (tenant_id, plan_id, status)
        SELECT t.id, p.id, 'active'
        FROM shared.tenants t, shared.plans p
        WHERE t.code = 'SPS001' AND p.code = 'internal'
        ON CONFLICT (tenant_id) DO NOTHING;
        """
    )

    # 5) Founder user — PASSWORD-LESS (sentinel hash, status 'invited').
    op.execute(
        f"""
        INSERT INTO shared.users (tenant_id, email, password_hash, full_name, status)
        SELECT t.id, '{FOUNDER_EMAIL}', '{SENTINEL_PW}', 'Sandeep Kumar', 'invited'
        FROM shared.tenants t
        WHERE t.code = 'SPS001'
        ON CONFLICT (tenant_id, email) DO NOTHING;
        """
    )

    # 6) Founder membership in all three BUs with role 'owner'.
    #    NOTE: 'owner' chosen for the founder/owner user — the architecture role
    #    matrix (Part 4) lists Founder/Super Admin/Admin but no canonical slug;
    #    'owner' matches the tenancy doc's "owner user". Revisit if RBAC fixes a slug.
    op.execute(
        f"""
        INSERT INTO shared.memberships (user_id, business_unit_id, roles)
        SELECT u.id, bu.id, ARRAY['owner']::text[]
        FROM shared.users u
        JOIN shared.tenants t  ON t.id = u.tenant_id AND t.code = 'SPS001'
        JOIN shared.business_units bu ON bu.tenant_id = t.id
        WHERE u.email = '{FOUNDER_EMAIL}'
        ON CONFLICT (user_id, business_unit_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Delete seed rows by natural keys, FK-safe order.
    op.execute(
        f"""
        DELETE FROM shared.memberships m
        USING shared.users u, shared.tenants t
        WHERE m.user_id = u.id AND u.tenant_id = t.id
          AND t.code = 'SPS001' AND u.email = '{FOUNDER_EMAIL}';
        """
    )
    op.execute(
        f"""
        DELETE FROM shared.users u USING shared.tenants t
        WHERE u.tenant_id = t.id AND t.code = 'SPS001' AND u.email = '{FOUNDER_EMAIL}';
        """
    )
    op.execute(
        """
        DELETE FROM shared.tenant_subscriptions ts USING shared.tenants t
        WHERE ts.tenant_id = t.id AND t.code = 'SPS001';
        """
    )
    op.execute(
        """
        DELETE FROM shared.business_units bu USING shared.tenants t
        WHERE bu.tenant_id = t.id AND t.code = 'SPS001';
        """
    )
    op.execute("DELETE FROM shared.plans WHERE code = 'internal';")
    op.execute("DELETE FROM shared.tenants WHERE code = 'SPS001';")
