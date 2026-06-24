from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    scada_base_url: str
    scada_username: str
    scada_password: str
    scada_request_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()