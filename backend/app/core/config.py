from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    scada_base_url: str
    scada_username: str
    scada_password: str
    scada_request_timeout_seconds: float = 10.0

    scada_history_sqlite_path: str = "data/scada_history.sqlite"

    # Future PostgreSQL archive source.
    # Currently optional because Phase 6B reads from local SQLite.
    scada_pg_host: str | None = None
    scada_pg_port: int = 5432
    scada_pg_database: str | None = None
    scada_pg_username: str | None = None
    scada_pg_password: str | None = None
    scada_pg_sslmode: str = "disable"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()