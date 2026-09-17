from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "API de Endereços"
    database_url: str
    viacep_base_url: str = "https://viacep.com.br/ws"
    http_timeout: float = Field(default=3.0, gt=0)
    # Tentativas totais (não adicionais) por consulta ao ViaCEP.
    viacep_tentativas: int = Field(default=3, ge=1, le=5)
    # Espera antes de repetir; dobra a cada nova tentativa.
    viacep_backoff_inicial: float = Field(default=0.2, ge=0)
    # Limite de requisições por cliente, por janela. 0 desliga o limite.
    rate_limit_requisicoes: int = Field(default=60, ge=0)
    rate_limit_janela: float = Field(default=60.0, gt=0)
    api_key: SecretStr

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
