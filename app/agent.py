# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Modified: the template's weather agent is replaced by the media_insights
# coordinator with specialists, a workflow pipeline, skills, memory, examples
# and app-level plugins.

"""media_insights: the platform's baseline multi-agent app.

media_insights (coordinator, LlmAgent)
├── analytics_agent         sub-agent (transfer): BigQuery MCP, read-only
├── rights_agent            sub-agent (transfer): content API via Apigee, state-based access check
├── weekly_brief_pipeline   AgentTool: SequentialAgent(collector -> LoopAgent(writer, reviewer))
├── report_writer           AgentTool: skills (inline, file-based, meta)
├── chart_analyst           AgentTool, optional: code execution sandbox
├── memory                  remember_preference, PreloadMemoryTool and/or load_memory
└── examples                ExampleTool over an Example Store, optional

App-level: guardrail plugin (Model Armor + call cap), Apigee key plugin, memory plugin,
context filter, event compaction, optional BigQuery agent analytics.
"""

import logging
import os

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps.app import EventsCompactionConfig
from google.adk.plugins.context_filter_plugin import ContextFilterPlugin
from google.adk.tools.agent_tool import AgentTool

from app.agents.specialists import analytics_agent, rights_agent
from app.agents.weekly_brief import weekly_brief_pipeline
from app.app_utils import services
from app.config import settings
from app.models import build_model, generation_config
from app.plugins.apigee import ApigeeKeyPlugin
from app.plugins.guardrails import ModelArmorGuardrailPlugin
from app.plugins.memory import MemoryPlugin
from app.skills_toolset import report_skills
from app.tools.memory_tools import memory_tools

MEMORY_ENABLED = services.memory_service_uri() is not None

report_writer = LlmAgent(
    name="report_writer",
    model=build_model(settings.fast_model),
    description="Writes or reformats a report from figures already in the conversation; can also draft new SKILL.md files.",
    instruction=(
        "You write reports and summaries using your skills. Always say which skill you used. "
        "Use only figures given to you; if figures are missing, say so."
    ),
    tools=[report_skills()],
)


def _optional_tools() -> list:
    tools = []
    if settings.example_store_name:
        # Few-shot examples retrieved per query from an Example Store (ch2 lab archive).
        from google.adk.examples.vertex_ai_example_store import VertexAiExampleStore
        from google.adk.tools.example_tool import ExampleTool

        tools.append(ExampleTool(VertexAiExampleStore(settings.example_store_name)))
    if settings.sandbox_resource_name:
        # Model-written code runs in an isolated sandbox, never on the runtime (Course 5).
        from google.adk.code_executors.agent_engine_sandbox_code_executor import (
            AgentEngineSandboxCodeExecutor,
        )

        chart_analyst = LlmAgent(
            name="chart_analyst",
            model=build_model(),
            description="Runs Python on numbers given to it (statistics, growth rates, charts). No data access of its own.",
            instruction="Write and run Python for the numbers you are given. Print results. Save charts as PNG.",
            code_executor=AgentEngineSandboxCodeExecutor(
                sandbox_resource_name=settings.sandbox_resource_name
            ),
        )
        tools.append(AgentTool(agent=chart_analyst))
    return tools


async def initialize_state(callback_context) -> None:
    """before_agent_callback: initialise state the instruction and tools read (agents-cli pattern).

    The front end normally writes user:business_unit at session creation. Evals and the
    dev UI have no front end, so DEFAULT_BUSINESS_UNIT can stand in; it is never used to
    overwrite a value the application set.
    """
    state = callback_context.state
    if "user:business_unit" not in state and settings.default_business_unit:
        state["user:business_unit"] = settings.default_business_unit
    if "user:preferences" not in state:
        state["user:preferences"] = []
    return None


INSTRUCTION = """You are the Media Insights coordinator for {user:display_name?} in the {user:business_unit?} business unit.

Route each request:
- Views, top titles, trends, business-unit totals -> transfer to analytics_agent.
- Where/until when a title may be streamed (distribution rights) -> transfer to rights_agent.
- A "brief", "weekly report" or "summary report" -> call weekly_brief_pipeline.
- Reformat or rewrite figures already in this conversation, or draft a new skill -> call report_writer.
- Calculations or charts on numbers you already have -> call chart_analyst if available.

Known preferences of this user: {user:preferences?}

Memory:
- If the user tells you a lasting preference or asks you to remember something, call remember_preference.
- Apply known preferences (format, length, focus) to every answer.
- Use load_memory when the user refers to something from an earlier conversation.

Rules: never answer factual questions from your own knowledge; if no tool can answer, say so.
Keep answers short and show the numbers behind them."""

root_agent = LlmAgent(
    # Keep in sync with create_params.root_agent_name in agents-cli-manifest.yaml:
    # telemetry reports this name as gen_ai.agent.name.
    name="media_insights",
    model=build_model(),
    description="Answers content-performance and distribution-rights questions from governed data.",
    instruction=INSTRUCTION,
    sub_agents=[analytics_agent(), rights_agent()],
    tools=[
        AgentTool(agent=weekly_brief_pipeline()),
        AgentTool(agent=report_writer),
        *memory_tools(MEMORY_ENABLED),
        *_optional_tools(),
    ],
    generate_content_config=generation_config(),
    before_agent_callback=initialize_state,
)

# --- App-level plugins: cross-cutting controls in one place (Course 4) ---
_plugins = [
    ModelArmorGuardrailPlugin(
        template_name=settings.model_armor_template_name,
        fail_open=settings.guardrail_fail_open,
        max_llm_calls=settings.max_llm_calls,
    ),
    MemoryPlugin(enabled=MEMORY_ENABLED and settings.save_memory_each_turn),
    # Keep the last N invocations in the model context (Course 6 ch. 4: sliding window).
    ContextFilterPlugin(num_invocations_to_keep=settings.keep_last_invocations),
]
if settings.use_apigee:
    _plugins.append(ApigeeKeyPlugin())

if settings.bq_analytics:
    # Initialize BigQuery Analytics (template option): agent events to BigQuery.
    try:
        from google.adk.plugins.bigquery_agent_analytics_plugin import (
            BigQueryAgentAnalyticsPlugin,
            BigQueryLoggerConfig,
        )
        from google.cloud import bigquery

        _dataset_id = os.environ.get("BQ_ANALYTICS_DATASET_ID", "adk_agent_analytics")
        bigquery.Client(project=settings.project).create_dataset(
            f"{settings.project}.{_dataset_id}", exists_ok=True
        )
        _plugins.append(
            BigQueryAgentAnalyticsPlugin(
                project_id=settings.project,
                dataset_id=_dataset_id,
                location=settings.region,
                config=BigQueryLoggerConfig(
                    gcs_bucket_name=os.environ.get("BQ_ANALYTICS_GCS_BUCKET"),
                    connection_id=os.environ.get("BQ_ANALYTICS_CONNECTION_ID"),
                ),
            )
        )
    except Exception as e:
        logging.warning(f"Failed to initialize BigQuery Analytics: {e}")

app = App(
    root_agent=root_agent,
    name="app",
    plugins=_plugins,
    # Summarise older events with an LLM every N invocations (Course 6 ch. 4: compaction).
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=settings.compaction_interval, overlap_size=1
    ),
    # Each agent keeps its own cached prompt prefix across transfers (Course 12: caching ROI).
    context_cache_config=ContextCacheConfig() if settings.context_cache else None,
)
