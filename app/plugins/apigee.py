"""Adds this deployment's Apigee API key to every model call (all agents, one place).

The key is read from Secret Manager at run time and attached per request through
GenerateContentConfig.http_options. It is never stored on the agent or model object,
so it never ends up in a deployment package.
"""

from __future__ import annotations

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

from app.tools.content_api import apigee_key


class ApigeeKeyPlugin(BasePlugin):
    def __init__(self):
        super().__init__(name="apigee_key")

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> LlmResponse | None:
        http_options = llm_request.config.http_options or types.HttpOptions()
        http_options.headers = {
            **(http_options.headers or {}),
            "x-apikey": apigee_key(),
        }
        llm_request.config.http_options = http_options
        return None
