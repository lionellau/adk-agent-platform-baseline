"""Release gate: the agent must pass its evalsets (run from the agents/ folder)."""
import asyncio
import os

import pytest
from google.adk.evaluation.agent_evaluator import AgentEvaluator

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(HERE, "..", "eval")


def test_analytics():
    asyncio.run(AgentEvaluator.evaluate(
        agent_module="media_insights",
        eval_dataset_file_path_or_dir=os.path.join(EVAL, "analytics", "analytics.evalset.json"),
        num_runs=1))


@pytest.mark.skipif(not os.environ.get("CONTENT_API_URL"), reason="needs Apigee (Phase 7)")
def test_rights():
    asyncio.run(AgentEvaluator.evaluate(
        agent_module="media_insights",
        eval_dataset_file_path_or_dir=os.path.join(EVAL, "rights", "rights.evalset.json"),
        num_runs=1))
