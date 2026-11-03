"""X1: create one Code Execution sandbox under the deployed agent engine and print its name.

Run once. If it prints PENDING, wait and look it up in the console; do not re-run (it would create a second sandbox).
Needs PROJECT_ID, REGION and AGENT_ENGINE in the environment (source ~/platform.env).
"""
import os

import vertexai
from vertexai import types

client = vertexai.Client(project=os.environ["PROJECT_ID"], location=os.environ["REGION"])
op = client.agent_engines.sandboxes.create(
    name=os.environ["AGENT_ENGINE"],
    config=types.CreateAgentEngineSandboxConfig(display_name="mc-analysis-sandbox"),
    spec={"code_execution_environment": {}},
)
print("SANDBOX_RESOURCE_NAME=" + (op.response.name if op.response else "PENDING"))
