"""A6 check: the agent package imports with its .env and is wired as the README expects.

Usage (from the repo root): python3 scripts/check_agent.py [agent_name]   # default media_insights
"""
import os
import sys

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = sys.argv[1] if len(sys.argv) > 1 else "media_insights"
ENV = os.path.join(ROOT, "agents", NAME, ".env")

load_dotenv(ENV, override=True)
bad = [k for k, v in os.environ.items() if "REPLACE_ME" in v]
assert not bad, f"placeholders left in {ENV}: {bad} (fill it in: README step 6)"
sys.path.insert(0, os.path.join(ROOT, "agents"))

module = __import__(f"{NAME}.agent", fromlist=["root_agent"])
r = module.root_agent
names = [getattr(t, "__name__", type(t).__name__) for t in r.tools]
print("agent:", r.name, "| model:", getattr(r.model, "model", r.model), "| tools:", names)
assert "McpToolset" in names and "get_content_rights" in names, names
assert ("PreloadMemoryTool" in names) == module.ENABLE_MEMORY, names
assert "{business_unit?}" in r.instruction and "__PROJECT__" not in r.instruction
assert r.before_agent_callback and r.after_model_callback and r.before_model_callback
print("A6 OK")
