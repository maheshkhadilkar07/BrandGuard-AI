"""Application settings, loaded from environment variables or a .env file.

No secret is hard-coded. SECRET_KEY must be supplied by the environment.
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    APP_NAME: str = "BrandGuard AI"
    DATABASE_URL: str = "postgresql+psycopg://brandguard:brandguard@localhost:5432/brandguard"
    SECRET_KEY: str  # required: no default on purpose
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    MAX_UPLOAD_MB: int = 10
    MAX_TEXT_CHARS: int = 200_000
    OCR_ENABLED: bool = True
    TESSERACT_CMD: str = ""  # e.g. C:\\Program Files\\Tesseract-OCR\\tesseract.exe (Windows, if not on PATH)

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Optional AI layer. Leave LLM_PROVIDER=none to use the rule engine only.
    LLM_PROVIDER: str = "none"  # none | openai_compatible
    LLM_API_BASE: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_TIMEOUT_SECONDS: int = 40

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_not_blank(cls, v: str) -> str:
        if len(v) < 16:
            raise ValueError("SECRET_KEY must be at least 16 characters")
        return v

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return self.LLM_PROVIDER != "none" and bool(self.LLM_API_KEY) and bool(self.LLM_MODEL)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
