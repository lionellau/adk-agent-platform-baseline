"""Settings for the agent platform, read once from the environment (.env locally).

Every switch the platform has lives here, so one file explains how a deployment is
configured. Nothing in this module holds a secret: keys come from Secret Manager.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Settings:
    project: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    )
    # Gemini location. Gemini 3.x models are served from "global".
    location: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    )
    # Regional services (Agent Runtime, Memory Bank, Model Armor) cannot use "global".
    region: str = field(default_factory=lambda: os.environ.get("REGION", "us-central1"))
    model: str = field(
        default_factory=lambda: os.environ.get("MODEL", "gemini-3.8-flash")
    )
    # A cheaper model for routing/writing steps (Course 12: task-based model routing).
    fast_model: str = field(
        default_factory=lambda: os.environ.get(
            "FAST_MODEL", os.environ.get("MODEL", "gemini-3.8-flash")
        )
    )

    # --- data and tools ---
    bq_dataset: str = field(
        default_factory=lambda: os.environ.get("BQ_DATASET", "media_analytics")
    )
    content_api_url: str = field(
        default_factory=lambda: os.environ.get("CONTENT_API_URL", "")
    )

    # --- gateway (Apigee) ---
    use_apigee: bool = field(default_factory=lambda: _flag("USE_APIGEE"))
    apigee_proxy_url: str = field(
        default_factory=lambda: os.environ.get("APIGEE_PROXY_URL", "")
    )
    apigee_key_secret: str = field(
        default_factory=lambda: os.environ.get("APIGEE_KEY_SECRET", "")
    )

    # --- guardrails ---
    model_armor_template: str = field(
        default_factory=lambda: os.environ.get("MA_TEMPLATE", "")
    )
    guardrail_fail_open: bool = field(
        default_factory=lambda: _flag("GUARDRAIL_FAIL_OPEN")
    )
    max_llm_calls: int = field(
        default_factory=lambda: int(os.environ.get("MAX_LLM_CALLS", "12"))
    )

    # --- memory ---
    # preload: recall every turn (proactive); tool: agent calls load_memory (reactive); both.
    memory_mode: str = field(
        default_factory=lambda: os.environ.get("MEMORY_MODE", "both")
    )
    save_memory_each_turn: bool = field(
        default_factory=lambda: _flag("SAVE_MEMORY_EACH_TURN", "true")
    )

    # --- context management (Course 6 ch. 4) ---
    keep_last_invocations: int = field(
        default_factory=lambda: int(os.environ.get("KEEP_LAST_INVOCATIONS", "20"))
    )
    compaction_interval: int = field(
        default_factory=lambda: int(os.environ.get("COMPACTION_INTERVAL", "8"))
    )

    # --- optional features ---
    example_store_name: str = field(
        default_factory=lambda: os.environ.get("EXAMPLE_STORE_NAME", "")
    )
    sandbox_resource_name: str = field(
        default_factory=lambda: os.environ.get("SANDBOX_RESOURCE_NAME", "")
    )
    bq_analytics: bool = field(default_factory=lambda: _flag("BQ_ANALYTICS"))
    context_cache: bool = field(default_factory=lambda: _flag("CONTEXT_CACHE"))
    # Token streaming from the model in /api/chat. Set false if a gateway can only
    # count tokens on non-streamed responses.
    stream_model_calls: bool = field(
        default_factory=lambda: _flag("STREAM_MODEL_CALLS", "true")
    )
    # Only for evals/dev, where no front end sets the business unit. Leave empty in production.
    default_business_unit: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_BUSINESS_UNIT", "")
    )

    @property
    def model_armor_template_name(self) -> str:
        if not (self.project and self.model_armor_template):
            return ""
        return f"projects/{self.project}/locations/{self.region}/templates/{self.model_armor_template}"


settings = Settings()
