"""Integration tests that call the real model are opt-in.

test_agent.py and test_server_e2e.py (from the agents-cli template) send real prompts to
Gemini, so they need Application Default Credentials, GOOGLE_CLOUD_PROJECT and the
Agent Platform API. Run them with:

    RUN_LIVE_TESTS=1 uv run pytest tests/integration/test_agent.py tests/integration/test_server_e2e.py

Postgres and ADK evalset tests have their own switches (PG_TEST_URL, RUN_LIVE_EVALS).
"""

import os

import pytest

LIVE_MODULES = {"test_agent.py", "test_server_e2e.py"}


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LIVE_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="live model test: set RUN_LIVE_TESTS=1 (needs ADC)")
    for item in items:
        if item.path.name in LIVE_MODULES:
            item.add_marker(skip)
