from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Presale Service"
    env: str = "dev"
    auto_create_tables: bool = True
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5434
    db_name: str = "presale_db"
    db_user: str = "presale"
    db_password: str = "presale"
    db_dsn: str | None = None
    jwt_secret_key: str = Field(default="change-me-in-prod", min_length=8)
    jwt_algorithm: str = "HS256"
    ai_service_url: str = "http://localhost:8003"
    minio_endpoint: str = "localhost:19000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "presale-files"
    minio_secure: bool = False

    model_config = SettingsConfigDict(env_file="../../.env", env_prefix="PRESALE_")

    @model_validator(mode="after")
    def build_database_url(self):
        if self.database_url:
            return self
        if self.db_dsn:
            self.database_url = self.db_dsn
        else:
            self.database_url = (
                f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return self


settings = Settings()
