"""Centralised env-driven settings (pydantic-settings).

Loaded from .env at process start. Never read os.environ directly elsewhere —
go through `settings` so missing keys fail loudly at boot.
"""
from __future__ import annotations

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== Service =====
    env: str = "dev"
    port: int = 8000
    log_level: str = "info"
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])

    # ===== Sentry =====
    sentry_dsn: str = ""

    # ===== Redis =====
    redis_url: str = "redis://localhost:6379/0"

    # ===== LLM =====
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    doubao_api_key: str = ""
    doubao_endpoint_id: str = ""
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    # ===== ASR =====
    xfyun_app_id: str = ""
    xfyun_api_key: str = ""
    xfyun_api_secret: str = ""
    aliyun_asr_app_key: str = ""
    aliyun_asr_ak_id: str = ""
    aliyun_asr_ak_secret: str = ""
    volc_asr_app_id: str = ""
    volc_asr_token: str = ""

    # ===== TTS =====
    aliyun_tts_ak_id: str = ""
    aliyun_tts_ak_secret: str = ""
    aliyun_tts_voice: str = "cosyvoice-v1"

    # ===== Subscription =====
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_mch_id: str = ""
    wechat_api_v3_key: str = ""
    apple_iap_shared_secret: str = ""

    # ===== Auth =====
    device_token_secret: str = "change-me-in-prod"


settings = Settings()
