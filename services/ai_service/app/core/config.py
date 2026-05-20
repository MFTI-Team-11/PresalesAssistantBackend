from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Service"
    env: str = "dev"
    auto_create_tables: bool = True
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5435
    db_name: str = "ai_db"
    db_user: str = "ai"
    db_password: str = "ai"
    db_dsn: str | None = None
    ai_provider: str = "gigachat"
    gigachat_credentials: str | None = None
    gigachat_access_token: str | None = None
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat"
    gigachat_oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_chat_url: str = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    gigachat_files_url: str = "https://gigachat.devices.sberbank.ru/api/v1/files"
    gigachat_timeout_seconds: float = 60.0
    gigachat_verify_ssl: bool = False
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1"
    openai_responses_url: str = "https://api.openai.com/v1/responses"
    openai_files_url: str = "https://api.openai.com/v1/files"
    openai_file_purpose: str = "assistants"
    openai_timeout_seconds: float = 60.0
    openai_stream_output_path: str | None = "/tmp/out.txt"

    model_config = SettingsConfigDict(env_file="../../.env", env_prefix="AI_")

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
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
