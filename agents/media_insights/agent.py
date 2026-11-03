"""media_insights: baseline agent for the agent platform sandbox."""
import os

import google.auth
import google.auth.transport.requests
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import Gemini, LlmRequest
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from . import guardrails, tools

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
DATASET = os.environ.get("BQ_DATASET", "media_analytics")
MODEL = os.environ.get("MODEL", "gemini-2.5-flash")
USE_APIGEE = os.environ.get("USE_APIGEE", "false").lower() == "true"
ENABLE_MEMORY = os.environ.get("ENABLE_MEMORY", "true").lower() == "true"

# ---- BigQuery remote MCP server (Google-managed, IAM-gated, read-only tools only) ----
_creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])


def _bq_mcp_headers(_ctx) -> dict:
    """Fresh OAuth token per call; tokens expire after about an hour on a long-running runtime."""
    if not _creds.valid:
        _creds.refresh(google.auth.transport.requests.Request())
    return {"Authorization": f"Bearer {_creds.token}", "x-goog-user-project": PROJECT}


bigquery_mcp = McpToolset(
    connection_params=StreamableHTTPConnectionParams(url="https://bigquery.googleapis.com/mcp", timeout=30),
    tool_filter=["list_table_ids", "get_table_info", "execute_sql_readonly"],
    header_provider=_bq_mcp_headers,
)


# ---- Model: direct Gemini (Phase 5) or through the Apigee model proxy (Phase 7+) ----
def _model():
    if USE_APIGEE:
        from google.adk.models.apigee_llm import ApigeeLlm
        # No key here: the agent object is pickled at deploy time, so the key is added per request.
        return ApigeeLlm(model=f"apigee/vertex_ai/v1/{MODEL}",  # v1 matches the proxy's flow condition
                         proxy_url=os.environ["APIGEE_PROXY_URL"])
    return Gemini(model=MODEL, retry_options=types.HttpRetryOptions(attempts=3))


def add_apigee_key(callback_context: CallbackContext, llm_request: LlmRequest):
    """before_model_callback: attach this BU's Apigee key, read from Secret Manager at run time."""
    if USE_APIGEE:
        ho = llm_request.config.http_options or types.HttpOptions()
        ho.headers = {**(ho.headers or {}), "x-apikey": tools.apigee_key()}
        llm_request.config.http_options = ho
    return None


async def save_to_memory(callback_context: CallbackContext):
    """after_agent_callback: send the session to the memory service (Memory Bank on Agent Runtime)."""
    try:
        if hasattr(callback_context, "add_session_to_memory"):
            await callback_context.add_session_to_memory()
        else:  # older ADK
            ic = callback_context._invocation_context
            if ic.memory_service:
                await ic.memory_service.add_session_to_memory(ic.session)
    except Exception as exc:  # memory must never break the answer
        guardrails.log.warning('{"event": "memory_error", "detail": "%s"}', repr(exc)[:200])
    return None


INSTRUCTION = """
You are the Media Insights agent. You help staff of the {business_unit?} business unit
understand content performance and distribution rights.

Data and tools:
- BigQuery dataset `__PROJECT__.__DATASET__` with tables content_catalogue (content_id, title,
  business_unit, genre, language, release_date, duration_min) and daily_viewership (view_date,
  content_id, platform, views, watch_minutes). Use execute_sql_readonly. Always set projectId to
  "__PROJECT__" and use fully qualified table names like `__PROJECT__.__DATASET__.daily_viewership`.
  Use get_table_info only if a query fails because of a column name.
- get_content_rights(content_id) for where and until when a title may be streamed. If you only
  know the title, look up its content_id in content_catalogue first.

Rules:
- Answer factual questions only from tool results, never from memory. If a tool returns nothing, say so.
- Show the numbers behind every answer and state the date range you used.
- If a question is ambiguous (which month, which business unit, which title), ask one short
  clarifying question before you query.
- You are read-only. Never try to create, change or delete data.
- If the user has told you a preference (format, length, language), follow it.
"""

root_agent = Agent(
    name="media_insights",
    model=_model(),
    description="Answers content-performance and distribution-rights questions from governed data.",
    instruction=INSTRUCTION.replace("__PROJECT__", PROJECT).replace("__DATASET__", DATASET),
    tools=[bigquery_mcp, tools.get_content_rights] + ([PreloadMemoryTool()] if ENABLE_MEMORY else []),
    generate_content_config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=2048),
    before_agent_callback=guardrails.screen_user_input,
    before_model_callback=[guardrails.cap_llm_calls, add_apigee_key],
    after_model_callback=guardrails.screen_model_output,
    after_agent_callback=save_to_memory,
)
