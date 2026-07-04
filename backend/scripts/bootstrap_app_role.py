"""One-off: provision the least-privilege `sps_app` DB role + grants.
Runs in the migrate task (connects as MASTER via DB_USER/DB_PASSWORD env); reads
the sps_app password from Secrets Manager via boto3. Idempotent."""
import json, os, boto3
from sqlalchemy import create_engine, text
from app.config import settings

secret_name = os.environ["APP_DB_SECRET_NAME"]
sm = boto3.client("secretsmanager", region_name=settings.aws_region)
pw = json.loads(sm.get_secret_value(SecretId=secret_name)["SecretString"])["password"]
assert pw.isalnum(), "expected alphanumeric password (special=false)"  # safe to interpolate

SCHEMAS = "shared, staffing, academy, consulting"
master = settings.db_user  # the role that creates future tables (migrations)
stmts = [
    "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='sps_app') "
    "THEN CREATE ROLE sps_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT; END IF; END $$;",
    f"ALTER ROLE sps_app WITH PASSWORD '{pw}';",
    f"GRANT USAGE ON SCHEMA {SCHEMAS} TO sps_app;",
    f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {SCHEMAS} TO sps_app;",
    f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {SCHEMAS} TO sps_app;",
    # Append-only ledgers: sps_app may INSERT/SELECT but never UPDATE/DELETE.
    # Master's default privileges (below) grant full DML on new tables, so every
    # new append-only table MUST be added here and the bootstrap re-run.
    "REVOKE UPDATE, DELETE ON shared.audit_logs, shared.consents FROM sps_app;",
    "REVOKE UPDATE, DELETE ON staffing.candidate_timeline FROM sps_app;",  # B.2
    f"ALTER DEFAULT PRIVILEGES FOR ROLE {master} IN SCHEMA {SCHEMAS} "
    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sps_app;",
    f"ALTER DEFAULT PRIVILEGES FOR ROLE {master} IN SCHEMA {SCHEMAS} "
    "GRANT USAGE, SELECT ON SEQUENCES TO sps_app;",
]
eng = create_engine(settings.database_url)
with eng.begin() as cx:
    for s in stmts:
        cx.execute(text(s))
print("OK bootstrap: sps_app created/synced + grants applied "
      "(append-only on audit_logs/consents/candidate_timeline)")
