"""Specialist sub-agents. The root agent hands the conversation to them (transfer).

With LLM-driven delegation the specialists write into the same session as the root
agent (shared history, Course 6 ch. 2), so a follow-up such as "and its rights?" works.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from app.models import build_model, generation_config
from app.tools.bigquery import bigquery_toolset, dataset_hint
from app.tools.content_api import get_content_rights


def analytics_agent() -> LlmAgent:
    return LlmAgent(
        name="analytics_agent",
        model=build_model(),
        description="Answers questions about views, watch time, top titles, trends and business-unit totals from BigQuery.",
        instruction=(
            "You answer content-performance questions for the {user:business_unit?} business unit.\n"
            + dataset_hint()
            + "\nRules: answer only from query results, never from memory; show the numbers and the "
            "date range you used; if the question is ambiguous (which month, which title), ask one "
            "short clarifying question first; you are read-only. When you are done, transfer back "
            "to media_insights if the user asks about something else."
        ),
        tools=[bigquery_toolset()],
        output_key="last_analytics_answer",
        generate_content_config=generation_config(),
    )


def rights_agent() -> LlmAgent:
    return LlmAgent(
        name="rights_agent",
        model=build_model(),
        description="Answers where and until when a title may be streamed or broadcast (distribution rights).",
        instruction=(
            "You answer distribution-rights questions.\n"
            "If you only know a title's name, find its content_id first:\n"
            + dataset_hint()
            + "\nThen call get_content_rights. If it returns status 'denied', tell the user their "
            "business unit may not read rights and do not guess. Give the regions and the expiry date."
        ),
        tools=[bigquery_toolset(), get_content_rights],
        output_key="last_rights_answer",
        generate_content_config=generation_config(),
    )
