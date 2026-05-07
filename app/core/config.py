from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class Settings:
    service_name: str = "ubid-backend"
    app_env: str = os.getenv("APP_ENV", "development")
    data_dir: Path = Path(os.getenv("DATA_DIR", "./data")).resolve()
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "").strip()
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip()
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    auto_link_threshold: int = int(os.getenv("AUTO_LINK_THRESHOLD", "85"))
    human_review_threshold: int = int(os.getenv("HUMAN_REVIEW_THRESHOLD", "60"))
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "12"))
    cors_origins: list[str] = field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]
    )
    extra_cors_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv("EXTRA_CORS_ORIGINS", "").split(",")
            if origin.strip()
        ]
    )

    @property
    def all_cors_origins(self) -> list[str]:
        return list(dict.fromkeys([*self.cors_origins, *self.extra_cors_origins]))

    @property
    def openrouter_configured(self) -> bool:
        return bool(self.openrouter_api_key)


settings = Settings()
