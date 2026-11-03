"""One place to build the model object for every agent: Gemini directly, or through Apigee.

USE_APIGEE=true routes model calls through the Apigee model proxy (design call path 1:
token quotas per business unit, routing, analytics). The API key is added per request
by ApigeeKeyPlugin, never stored here.
"""

from __future__ import annotations

from google.adk.models import Gemini
from google.genai import types

from app.config import settings


def build_model(model_id: str | None = None):
    model_id = model_id or settings.model
    if settings.use_apigee:
        from google.adk.models.apigee_llm import ApigeeLlm

        # "v1" makes the request path match the proxy's flow condition.
        return ApigeeLlm(
            model=f"apigee/vertex_ai/v1/{model_id}", proxy_url=settings.apigee_proxy_url
        )
    return Gemini(model=model_id, retry_options=types.HttpRetryOptions(attempts=3))


def generation_config(max_output_tokens: int = 2048) -> types.GenerateContentConfig:
    """Low temperature for factual answers; an output cap is a cost control (Course 12)."""
    return types.GenerateContentConfig(
        temperature=0.2, max_output_tokens=max_output_tokens
    )
