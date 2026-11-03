"""The weekly brief as an ADK 2.0 graph Workflow (Course 4: graph workflows).

Used as a standalone job (no chat), for example from Cloud Scheduler:
    python -m scripts.run_weekly_brief --business-unit news

    START -> brief_data_collector -> brief_writer -> publish_brief (function node)

The chat coordinator uses the SequentialAgent/LoopAgent version in
app/agents/weekly_brief.py, because ADK 2.13 cannot yet nest a Workflow under an
LlmAgent. Move it here when that becomes possible.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.workflow import START, Workflow

from app.config import settings
from app.models import build_model, generation_config
from app.skills_toolset import report_skills
from app.tools.bigquery import bigquery_toolset, dataset_hint


def publish_brief(brief_draft: str, brief_data: str = "") -> dict:
    """Function node: parameters are read from session state by name.

    Returns the record a scheduler or downstream system would store (e-mail, CMS, Slack).
    """
    return {
        "brief": brief_draft,
        "figures_used": brief_data,
        "chars": len(brief_draft or ""),
    }


def weekly_brief_graph() -> Workflow:
    collector = LlmAgent(
        name="brief_data_collector",
        model=build_model(),
        instruction=(
            "Collect the figures for this week's content performance brief for the "
            "{user:business_unit?} business unit.\n"
            + dataset_hint()
            + "\nOutput only the figures."
        ),
        tools=[bigquery_toolset()],
        output_key="brief_data",
        generate_content_config=generation_config(),
    )
    writer = LlmAgent(
        name="brief_writer",
        model=build_model(settings.fast_model),
        instruction=(
            "Write a content performance brief using only these figures:\n{brief_data}\n"
            "Load and follow the content-performance-report and number-formatting skills."
        ),
        tools=[report_skills()],
        output_key="brief_draft",
        generate_content_config=generation_config(),
    )
    return Workflow(
        name="weekly_brief_graph",
        description="Collect figures, write the brief, publish it.",
        edges=[(START, collector, writer, publish_brief)],
    )
