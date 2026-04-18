from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "development"
    base_url: str = "http://localhost:8000"
    log_level: str = "DEBUG"

    telegram_bot_token: str
    database_url: str
    deepseek_api_key: str
    openai_api_key: str

    langfuse_secret_key: str
    langfuse_public_key: str
    langfuse_host: str = "https://us.cloud.langfuse.com"

    google_service_account_json: str
    google_calendar_id: str = "primary"
    gmail_sender: str
    gmail_app_password: str

    dealership_name: str = "Our Dealership"
    dealership_address: str = "123 Main Street"

    default_timezone: str = "America/New_York"


settings = Settings()
