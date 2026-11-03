"""Release gate: the ADK evalsets must pass (real model and services). Skipped unless RUN_LIVE_EVALS=1.

Run: RUN_LIVE_EVALS=1 uv run pytest tests/integration/test_adk_evalsets.py
Needs a filled .env (GOOGLE_CLOUD_PROJECT, MODEL, BQ dataset loaded, Model Armor template;
the rights set also needs Apigee: CONTENT_API_URL). Thresholds come from each folder's
test_config.json, so `adk eval`, pytest and CI use the same numbers.
"""

from __future__ import annotations

import asyncio
import os
import pathlib

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_EVALS") != "1",
    reason="set RUN_LIVE_EVALS=1 to run live evals",
)
ADK_EVALS = pathlib.Path(__file__).resolve().parents[1] / "eval" / "adk"


@pytest.mark.parametrize("name", ["analytics", "memory", "rights"])
def test_evalset(name):
    if name == "rights" and not os.environ.get("CONTENT_API_URL"):
        pytest.skip("rights evalset needs the Apigee content API (CONTENT_API_URL)")
    from google.adk.evaluation.agent_evaluator import AgentEvaluator

    asyncio.run(
        AgentEvaluator.evaluate(
            agent_module="app",
            eval_dataset_file_path_or_dir=str(
                ADK_EVALS / name / f"{name}.evalset.json"
            ),
            num_runs=1,
        )
    )
