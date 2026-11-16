from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ORION API"
    environment: str = "development"
    pncp_base_url: str = "https://pncp.gov.br/api/consulta"
    pncp_domain_base_url: str = "https://pncp.gov.br/api/pncp"
    pncp_timeout_seconds: float = 25.0
    pncp_max_page_size: int = 50
    pncp_max_document_bytes: int = 26214400
    database_url: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    model_config = SettingsConfigDict(env_prefix="ORION_", env_file=".env", extra="ignore")


settings = Settings()
