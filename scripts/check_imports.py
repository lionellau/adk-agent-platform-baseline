"""S3 check: every library the platform uses imports, and the ADK is new enough."""
import importlib
import inspect

MODULES = ["google.adk", "google.adk.models.apigee_llm", "google.adk.tools.mcp_tool",
           "google.adk.tools.preload_memory_tool", "vertexai", "google.cloud.modelarmor_v1",
           "google.cloud.secretmanager"]

for name in MODULES:
    importlib.import_module(name)

import google.adk  # noqa: E402
from google.adk.tools.mcp_tool import McpToolset  # noqa: E402

assert "header_provider" in inspect.signature(McpToolset.__init__).parameters, \
    "ADK too old: McpToolset has no header_provider"
print("imports OK, google-adk", google.adk.__version__)
