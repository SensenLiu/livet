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

    # ===== Voice stack (ASR + TTS) — single vendor: 豆包 / 火山引擎 =====
    # ASR uses Volcengine real-time speech (SAMI streaming).
    # TTS uses Volcengine voice synthesis large model (CosyVoice-style).
    # Both authenticate via AK/SK signing — distinct from LLM bearer token.
    # Console: https://console.volcengine.com/speech/
    volc_ak_id: str = ""
    volc_sk: str = ""
    volc_asr_app_id: str = ""
    volc_asr_cluster: str = "volcengine_streaming_common"
    volc_tts_app_id: str = ""
    volc_tts_voice: str = "zh_female_qingxin_v2_mars_bigtts"

    # ===== Subscription =====
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_mch_id: str = ""
    wechat_api_v3_key: str = ""
    apple_iap_shared_secret: str = ""

    # ===== Auth =====
    device_token_secret: str = "change-me-in-prod"


settings = Settings()
