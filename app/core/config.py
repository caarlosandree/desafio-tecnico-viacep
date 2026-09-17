from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "desafio-viacep"
    database_url: str
    viacep_base_url: str = "https://viacep.com.br/ws"
    http_timeout: float = 5.0
    api_key: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache
def get_settings() -> Settings:
    return Settings()