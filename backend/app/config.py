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
    storage_bucket: str = "sps-technosoft-dev-storage"

    @property
    def database_url(self) -> str:
        return (f"postgresql+psycopg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}")


settings = Settings()
