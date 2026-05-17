from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Auth Service"
    env: str = "dev"
    auto_create_tables: bool = True
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5433
    db_name: str = "auth_db"
    db_user: str = "auth"
    db_password: str = "auth"
    db_dsn: str | None = None
    jwt_secret_key: str = Field(default="change-me-in-prod", min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 30
    access_cookie_name: str = "access_token"
    refresh_cookie_name: str = "refresh_token"
    cookie_secure: bool = False
    cookie_httponly: bool = True
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None
    cookie_path: str = "/"

    model_config = SettingsConfigDict(env_file="../../.env", env_prefix="AUTH_")

    @field_validator("cookie_domain", mode="before")
    @classmethod
    def empty_cookie_domain_as_none(cls, value):
        return None if value == "" else value

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
