"""Create a Code Execution sandbox under an Agent Runtime engine (Course 5) and print its name.

Usage: uv run python scripts/create_sandbox.py   (AGENT_ENGINE set; run once)
Then set SANDBOX_RESOURCE_NAME in .env to enable the chart_analyst agent.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()  # the repo's .env; variables already set in the shell win


def main() -> int:
    import agentplatform

    from app.app_utils.services import (
        agent_engine_resource_name,
        agent_runtime_location,
    )

    engine = agent_engine_resource_name()
    if not engine:
        print("FIX: set AGENT_ENGINE first")
        return 1
    client = agentplatform.Client(
        project=os.environ["GOOGLE_CLOUD_PROJECT"], location=agent_runtime_location()
    )
    op = client.sandboxes.create(
        name=engine,
        spec={"code_execution_environment": {}},
        config={"display_name": "mc-analysis-sandbox"},
    )
    name = getattr(getattr(op, "response", None), "name", None) or getattr(
        op, "name", None
    )
    print(f"SANDBOX_RESOURCE_NAME={name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
