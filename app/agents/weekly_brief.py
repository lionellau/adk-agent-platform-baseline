"""A workflow agent (Course 4: workflow agents orchestrate without a model deciding).

weekly_brief_pipeline = SequentialAgent:
  1. brief_data_collector  queries BigQuery, saves the figures to state["brief_data"]
  2. draft_and_review      LoopAgent (max 2 rounds):
       brief_writer    writes from {brief_data} using the report skills -> state["brief_draft"]
       brief_reviewer  checks the draft against the data; calls exit_loop when it passes

Agents hand over through session state (output_key + {key} placeholders), not through
the coordinator: the state schema is the contract between steps.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools import exit_loop

from app.config import settings
from app.models import build_model, generation_config
from app.skills_toolset import report_skills
from app.tools.bigquery import bigquery_toolset, dataset_hint


def weekly_brief_pipeline() -> SequentialAgent:
    collector = LlmAgent(
        name="brief_data_collector",
        model=build_model(),
        instruction=(
            "Collect the figures for a content performance brief for the {user:business_unit?} "
            "business unit (if empty, all units) for the period the user asked about.\n"
            + dataset_hint()
            + "\nReturn: total views per title for the period, ranked; views per week for the top 3 "
            "titles; total views per business unit. Output only the figures, as a compact list."
        ),
        tools=[bigquery_toolset()],
        output_key="brief_data",
        generate_content_config=generation_config(),
    )
    writer = LlmAgent(
        name="brief_writer",
        model=build_model(settings.fast_model),
        instruction=(
            "Write a content performance brief using only these figures:\n{brief_data}\n\n"
            "Load and follow the content-performance-report and number-formatting skills. "
            "If a reviewer note exists, fix it: {brief_review?}"
        ),
        tools=[report_skills()],
        output_key="brief_draft",
        generate_content_config=generation_config(),
    )
    reviewer = LlmAgent(
        name="brief_reviewer",
        model=build_model(settings.fast_model),
        instruction=(
            "Check this draft:\n{brief_draft}\n\nagainst these figures:\n{brief_data}\n\n"
            "If every number in the draft matches the figures and the date range is stated, call "
            "exit_loop. Otherwise reply with one short note saying what to fix."
        ),
        tools=[exit_loop],
        output_key="brief_review",
    )
    return SequentialAgent(
        name="weekly_brief_pipeline",
        description="Builds a checked content performance brief: collect figures, draft, review.",
        sub_agents=[
            collector,
            LoopAgent(
                name="draft_and_review", sub_agents=[writer, reviewer], max_iterations=2
            ),
        ],
    )
