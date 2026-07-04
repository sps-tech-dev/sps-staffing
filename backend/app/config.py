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

    # DPDP erasure auto-purge retention period (days). DELIBERATELY None — auto-purge
    # is a STUB pending legally-confirmed retention periods (GST/TDS/DPDP). Never guess.
    dpdp_retention_days: int | None = None   # DPDP_RETENTION_DAYS

    @property
    def database_url(self) -> str:
        return (f"postgresql+psycopg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}")


settings = Settings()
