"""Model Armor guardrails and a model-call cap, as one plugin for every agent in the app.

- before_run: screens the user's message once per turn. A blocked message ends the run
  with a refusal, so no agent, tool or model sees it (design: screen input first).
- before_model: caps model calls per turn (design: ADK's limit on model calls per run).
- after_model: screens final text answers, not tool calls or partial chunks.

Fails closed when Model Armor cannot be reached, unless GUARDRAIL_FAIL_OPEN=true.
"""

from __future__ import annotations

import json
import logging

from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

from app.config import settings

log = logging.getLogger("app.guardrails")

BLOCK_MESSAGE = (
    "I can't help with that request. It was blocked by the AI safety policy. "
    "Please rephrase your question about content performance or rights."
)
CAP_MESSAGE = (
    "I stopped because this request needed too many steps. Please narrow the question."
)


def _text(content: types.Content | None) -> str:
    if not content or not content.parts:
        return ""
    return "\n".join(p.text or "" for p in content.parts if getattr(p, "text", None))


class ModelArmorGuardrailPlugin(BasePlugin):
    def __init__(
        self, template_name: str = "", fail_open: bool = False, max_llm_calls: int = 12
    ):
        super().__init__(name="model_armor_guardrails")
        self.template_name = template_name
        self.fail_open = fail_open
        self.max_llm_calls = max_llm_calls
        self._client = None

    # --- Model Armor ---
    def _ma(self):
        if self._client is None:
            from google.api_core.client_options import ClientOptions
            from google.cloud import modelarmor_v1

            location = self.template_name.split("/")[3]
            self._client = modelarmor_v1.ModelArmorClient(
                client_options=ClientOptions(
                    api_endpoint=f"modelarmor.{location}.rep.googleapis.com",
                    quota_project_id=settings.project or None,
                )
            )
        return self._client

    def matched(self, stage: str, text: str) -> bool:
        """True when Model Armor finds a match (or cannot be reached and we fail closed)."""
        if not self.template_name:
            return False  # guardrail not configured (local dev without Model Armor)
        try:
            from google.cloud import modelarmor_v1

            if stage == "input":
                res = self._ma().sanitize_user_prompt(
                    request=modelarmor_v1.SanitizeUserPromptRequest(
                        name=self.template_name,
                        user_prompt_data=modelarmor_v1.DataItem(text=text),
                    )
                )
            else:
                res = self._ma().sanitize_model_response(
                    request=modelarmor_v1.SanitizeModelResponseRequest(
                        name=self.template_name,
                        model_response_data=modelarmor_v1.DataItem(text=text),
                    )
                )
            return (
                res.sanitization_result.filter_match_state
                == modelarmor_v1.FilterMatchState.MATCH_FOUND
            )
        except Exception as exc:  # network, permission, quota
            self.audit(stage, "error", repr(exc))
            return not self.fail_open

    @staticmethod
    def audit(stage: str, verdict: str, detail: str = "") -> None:
        # One JSON line per decision; a log-based metric counts guardrail_block lines.
        log.warning(
            json.dumps(
                {
                    "event": f"guardrail_{verdict}",
                    "stage": stage,
                    "detail": detail[:200],
                }
            )
        )

    # --- hooks ---
    async def before_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> types.Content | None:
        text = _text(invocation_context.user_content)
        if text and self.matched("input", text):
            self.audit("input", "block")
            return types.Content(role="model", parts=[types.Part(text=BLOCK_MESSAGE)])
        return None

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> LlmResponse | None:
        calls = int(callback_context.state.get("temp:llm_calls", 0)) + 1
        callback_context.state["temp:llm_calls"] = calls
        if calls > self.max_llm_calls:
            self.audit("model", "cap", f"calls={calls}")
            return LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text=CAP_MESSAGE)]
                )
            )
        return None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        content = llm_response.content
        if llm_response.partial or not content or not content.parts:
            return None
        if any(getattr(p, "function_call", None) for p in content.parts):
            return None
        text = _text(content)
        if text and self.matched("output", text):
            self.audit("output", "block")
            return LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part(text=BLOCK_MESSAGE)]
                )
            )
        return None
