from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    env: str = "dev"
    aws_region: str = "ap-south-1"
    app_base_domain: str = "spstechnosoft.com"

    # Data tier connection config. Read from env (DB_HOST, DB_PORT, ...) with
    # safe localhost defaults so the app ALWAYS boots even if these are absent
    # or the data tier is unreachable. No connection is made here.
    db_host: str = "localhost"      # DB_HOST     (RDS endpoint, no :port)
    db_port: int = 5432             # DB_PORT
    db_name: str = "sps_platform_dev"  # DB_NAME
    db_user: str = "sps"            # DB_USER     (injected from Secrets Manager)
    db_password: str = "change-me"  # DB_PASSWORD (injected from Secrets Manager)

    redis_host: str = "localhost"   # REDIS_HOST  (ElastiCache primary endpoint)
    redis_port: int = 6379          # REDIS_PORT

    jwt_access_secret: str = "change-me-access"
    jwt_refresh_secret: str = "change-me-refresh"
    # A3 — SEPARATE academy-student auth (Option 1). A DISTINCT signing secret from
    # jwt_access_secret so an academy token cryptographically FAILS verification in
    # the staffing resolver (and vice-versa) — the token boundary is cryptographic,
    # not just claim-based; a forgotten `kind` check still fails closed.
    jwt_academy_secret: str = "change-me-academy"    # JWT_ACADEMY_SECRET
    access_ttl_seconds: int = 900       # 15 min
    refresh_ttl_seconds: int = 604800   # 7 days
    cookie_secure: bool = False         # COOKIE_SECURE — true in prod (HTTPS only)
    # S3 storage bucket. Deployed tasks inject S3_BUCKET (ecs.tf); the alias fixes
    # the PENDING C5 mismatch where the field only read STORAGE_BUCKET and silently
    # fell back to this default on ECS. Default is for local/test only.
    storage_bucket: str = Field(
        default="sps-technosoft-dev-storage",
        validation_alias=AliasChoices("S3_BUCKET", "STORAGE_BUCKET"),
    )

    # Feature flags (F6). Non-GA features default OFF; gated routes 404 when off
    # (see app/features.py). AI assistive widgets are not GA — off in dev.
    feature_ai: bool = False            # FEATURE_AI
    # B.7 admin assessment waiver — a GOVERNED per-tenant capability (demo/policy
    # toggle): admin-gated, reason-required, audited, never fakes a score. OFF by
    # default; 404 when off (probe-proof).
    feature_assessment_waiver: bool = False   # FEATURE_ASSESSMENT_WAIVER
    # A1 EdTech/Academy vertical — the whole academy surface is gated behind this;
    # OFF by default → /api/academy/* 404s (probe-proof). Per-tenant-capable
    # signature (like the AI/waiver flags); env-global today.
    feature_academy: bool = False             # FEATURE_ACADEMY
    # A3 academy admin alert recipient (config, not hardcoded). Real SES = Part-D.
    academy_admin_email: str = "academy@spstechnosoft.com"   # ACADEMY_ADMIN_EMAIL

    # PII field encryption (Part 10). Envelope encryption + blind index.
    #   - PII_KMS_KEY_ID set  -> KMS mode (GenerateDataKey/Decrypt on the CMK).
    #   - PII_KMS_KEY_ID empty -> LOCAL mode (fixed dev key; NOT for prod) so the
    #     local loop + tests run without AWS.
    #   - PII_INDEX_KEY: HMAC-SHA256 key for blind indexes (deterministic exact
    #     match / dedup). In prod injected from Secrets Manager; separate from the
    #     encryption key on purpose.
    pii_kms_key_id: str = ""            # PII_KMS_KEY_ID (CMK id/arn/alias)
    pii_index_key: str = ""            # PII_INDEX_KEY  (base64 or raw)
    pii_local_dek: str = ""            # PII_LOCAL_DEK  (base64; local mode only)

    # hCaptcha bot gate on public registration (Part: anti-abuse).
    #   - HCAPTCHA_SECRET set  -> real server-side verification (siteverify).
    #   - empty                -> LOCAL test mode: a non-empty token passes (no
    #     external call) so the gate mechanism is exercised in tests. Real keys
    #     are STOP-4 (hCaptcha account). HCAPTCHA_SITEKEY is exposed to the client.
    hcaptcha_secret: str = ""           # HCAPTCHA_SECRET
    hcaptcha_sitekey: str = ""          # HCAPTCHA_SITEKEY (public; client widget)

    # Fuzzy duplicate detection (B.3): pg_trgm name-similarity threshold. A hit also
    # requires a SECOND signal (skill overlap / resume-text similarity) — name alone
    # never flags. Conservative default; tune with real data.
    dedup_name_similarity: float = 0.4       # DEDUP_NAME_SIMILARITY
    dedup_resume_similarity: float = 0.3     # DEDUP_RESUME_SIMILARITY (second signal)

    # Aptitude test engine (B.7) — Appendix A / Compendium §14 defaults.
    test_question_count: int = 30        # TEST_QUESTION_COUNT (capped by available bank size)
    test_time_limit_minutes: int = 60    # TEST_TIME_LIMIT_MINUTES
    test_pass_threshold: float = 0.70    # TEST_PASS_THRESHOLD (no negative marking)
    test_link_ttl_hours: int = 72        # TEST_LINK_TTL_HOURS (one-time link validity)
    test_retake_cooldown_days: int = 30  # TEST_RETAKE_COOLDOWN_DAYS (after a fail)
    test_max_snapshots: int = 500        # TEST_MAX_SNAPSHOTS (proctoring uploads per test)
    # A4 — academy entrance aptitude config (60Q/60min; staffing stays 30Q/60min).
    # Course-INDEPENDENT bank (quant/logical/verbal/English); reuses the B.7 engine.
    academy_test_question_count: int = 60         # ACADEMY_TEST_QUESTION_COUNT
    academy_test_time_limit_minutes: int = 60     # ACADEMY_TEST_TIME_LIMIT_MINUTES

    # Notification service (B.10). ConsoleChannel is the ONLY implemented channel;
    # the override routes ALL enqueues to it (dev sink). Part D: set the override
    # empty + register real channels — enqueued rows for real channel types are
    # parked pending until their channel registers (zero call-site change).
    notify_channel_override: str = "console"   # NOTIFY_CHANNEL_OVERRIDE ("" = template channel)
    notify_max_attempts: int = 5               # NOTIFY_MAX_ATTEMPTS (then status=failed)

    # Commercial layer (B.9). Fee model is founder-confirmed (Part 0-FEE): base =
    # ANNUAL CTC, 15% flat default before tax, client-level override, GST/TDS inert.
    placement_guarantee_days: int = 60   # PLACEMENT_GUARANTEE_DAYS
    invoice_overdue_days: int = 30       # INVOICE_OVERDUE_DAYS (dunning detection)
    # B.13: GLOBAL vendor-commission default (% of the PLACEMENT FEE). Shipped
    # None ON PURPOSE — with no override/client-rate/valid-contract, accrual is
    # refused (409) rather than inventing a commercial term. Set the env when
    # the founder names a number.
    vendor_commission_default_percent: float | None = None  # VENDOR_COMMISSION_DEFAULT_PERCENT

    # DPDP erasure auto-purge retention period (days). DELIBERATELY None — auto-purge
    # is a STUB pending legally-confirmed retention periods (GST/TDS/DPDP). Never guess.
    dpdp_retention_days: int | None = None   # DPDP_RETENTION_DAYS

    @property
    def database_url(self) -> str:
        return (f"postgresql+psycopg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}")


settings = Settings()
