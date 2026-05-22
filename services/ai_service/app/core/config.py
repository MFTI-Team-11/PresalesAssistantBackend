from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Service"
    env: str = "dev"
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


settings = Settings()
