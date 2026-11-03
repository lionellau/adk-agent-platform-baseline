"""Guardrail callbacks: Model Armor on input and output, and a cap on model calls per turn."""
import json
import logging
import os
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.api_core.client_options import ClientOptions
from google.cloud import modelarmor_v1
from google.genai import types

log = logging.getLogger("media_insights.guardrails")

_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
_MA_LOCATION = os.environ.get("MA_LOCATION", "us-central1")
_TEMPLATE = (f"projects/{_PROJECT}/locations/{_MA_LOCATION}/templates/"
             f"{os.environ.get('MA_TEMPLATE', 'mc-agent-io')}")
_FAIL_OPEN = os.environ.get("GUARDRAIL_FAIL_OPEN", "false").lower() == "true"
_MAX_LLM_CALLS = int(os.environ.get("MAX_LLM_CALLS", "8"))

BLOCK_MESSAGE = ("I can't help with that request. It was blocked by the AI safety policy. "
                 "Please rephrase your question about content performance or rights.")
_client: Optional[modelarmor_v1.ModelArmorClient] = None


def _ma() -> modelarmor_v1.ModelArmorClient:
    global _client
    if _client is None:
        _client = modelarmor_v1.ModelArmorClient(client_options=ClientOptions(
            api_endpoint=f"modelarmor.{_MA_LOCATION}.rep.googleapis.com",
            quota_project_id=_PROJECT or None))
    return _client


def _audit(stage: str, verdict: str, detail: str = "") -> None:
    # One JSON line per decision: a log-based metric counts these (Phase 10).
    log.warning(json.dumps({"event": "guardrail_" + verdict, "stage": stage, "detail": detail[:200]}))


def _matched(stage: str, text: str) -> bool:
    """True when Model Armor finds a match. Fail closed unless GUARDRAIL_FAIL_OPEN=true."""
    try:
        if stage == "input":
            res = _ma().sanitize_user_prompt(request=modelarmor_v1.SanitizeUserPromptRequest(
                name=_TEMPLATE, user_prompt_data=modelarmor_v1.DataItem(text=text)))
        else:
            res = _ma().sanitize_model_response(request=modelarmor_v1.SanitizeModelResponseRequest(
                name=_TEMPLATE, model_response_data=modelarmor_v1.DataItem(text=text)))
        return res.sanitization_result.filter_match_state == modelarmor_v1.FilterMatchState.MATCH_FOUND
    except Exception as exc:  # network, permission, quota
        _audit(stage, "error", repr(exc))
        return not _FAIL_OPEN


def _text(content: Optional[types.Content]) -> str:
    if not content or not content.parts:
        return ""
    return "\n".join(p.text for p in content.parts if getattr(p, "text", None))


def screen_user_input(callback_context: CallbackContext) -> Optional[types.Content]:
    """before_agent_callback: returning Content skips the agent and answers with it."""
    text = _text(callback_context.user_content)
    if text and _matched("input", text):
        _audit("input", "block")
        return types.Content(role="model", parts=[types.Part(text=BLOCK_MESSAGE)])
    return None


def cap_llm_calls(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """before_model_callback: stop runaway tool loops (design: ADK limit on model calls per run)."""
    n = int(callback_context.state.get("temp:llm_calls", 0)) + 1
    callback_context.state["temp:llm_calls"] = n
    if n > _MAX_LLM_CALLS:
        _audit("model", "cap", f"calls={n}")
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(
            text="I stopped because this request needed too many steps. Please narrow the question.")]))
    return None


def screen_model_output(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
    """after_model_callback: screen final text answers (not tool calls, not partial chunks)."""
    content = llm_response.content
    if llm_response.partial or not content or not content.parts:
        return None
    if any(getattr(p, "function_call", None) for p in content.parts):
        return None
    text = _text(content)
    if text and _matched("output", text):
        _audit("output", "block")
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=BLOCK_MESSAGE)]))
    return None
