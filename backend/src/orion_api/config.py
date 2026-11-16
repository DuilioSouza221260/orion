from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ORION API"
    environment: str = "development"
    pncp_base_url: str = "https://pncp.gov.br/api/consulta"
    pncp_timeout_seconds: float = 25.0
    pncp_max_page_size: int = 50

    model_config = SettingsConfigDict(env_prefix="ORION_", env_file=".env", extra="ignore")


settings = Settings()
