from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    app_env: str = Field(default='local', min_length=2, max_length=20)
    app_name: str = Field(default='Korean History AI Server', min_length=1, max_length=80)
    app_version: str = Field(default='0.1.0', min_length=1, max_length=20)

    openai_api_key: SecretStr | None = None
    openai_model: str = Field(default='gpt-5.5', min_length=2, max_length=80)
    openai_timeout_seconds: float = Field(default=30.0, ge=5.0, le=120.0)
    openai_max_output_tokens: int = Field(default=3000, ge=500, le=12000)

    allowed_origins: list[str] = Field(default_factory=lambda: ['http://localhost:3000'])
    allowed_hosts: list[str] = Field(default_factory=lambda: ['localhost', '127.0.0.1'])

    rate_limit_max_requests: int = Field(default=30, ge=1, le=300)
    rate_limit_window_seconds: int = Field(default=60, ge=10, le=3600)
    max_request_body_bytes: int = Field(default=20_000, ge=1_000, le=1_000_000)

    @field_validator('allowed_origins', 'allowed_hosts', mode='before')
    @classmethod
    def split_csv(cls, value: Any) -> list[str]:
        if value is None or value == '':
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        if isinstance(value, list):
            return value
        raise ValueError('쉼표로 구분된 문자열 또는 문자열 배열이어야 합니다.')

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {'prod', 'production'}


@lru_cache
def get_settings() -> Settings:
    return Settings()
