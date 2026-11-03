"""Create (or update) an agent package on Agent Runtime with Memory Bank, telemetry and a dedicated SA.

Usage (from the repo root, after `source ~/platform.env`):
  python3 deploy/deploy.py                                      # agents/media_insights, create or update $AGENT_ENGINE
  AGENT_PKG=rights_desk AGENT_ENGINE= python3 deploy/deploy.py  # another agent folder, always a new engine
"""
import importlib
import os
import sys

import vertexai
from dotenv import dotenv_values
from vertexai import agent_engines

AGENT_PKG = os.environ.get("AGENT_PKG", "media_insights")
HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.normpath(os.path.join(HERE, "..", "agents"))
if not os.path.isdir(os.path.join(AGENTS, AGENT_PKG)):
    sys.exit(f"FIX: no agent folder agents/{AGENT_PKG}")
ENV = dotenv_values(os.path.join(AGENTS, AGENT_PKG, ".env"))
os.environ.update({k: v for k, v in ENV.items() if v})
sys.path.insert(0, AGENTS)
os.chdir(AGENTS)  # extra_packages paths are relative to this folder
root_agent = importlib.import_module(f"{AGENT_PKG}.agent").root_agent

PROJECT, REGION = os.environ["PROJECT_ID"], os.environ["REGION"]
PASS_THROUGH = ["GOOGLE_GENAI_USE_VERTEXAI", "MODEL", "BQ_DATASET", "MA_LOCATION", "MA_TEMPLATE",
                "MAX_LLM_CALLS", "GUARDRAIL_FAIL_OPEN", "ENABLE_MEMORY", "USE_APIGEE",
                "APIGEE_PROXY_URL", "APIGEE_KEY_SECRET", "CONTENT_API_URL"]
env_vars = {k: ENV[k] for k in PASS_THROUGH if ENV.get(k)}
env_vars.update({
    "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
    "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
})
memory_bank_config = {
    # Remember preferences and explicit instructions only; no personal-info topic (privacy by default).
    "customization_configs": [{"memory_topics": [
        {"managed_memory_topic": {"managed_topic_enum": "USER_PREFERENCES"}},
        {"managed_memory_topic": {"managed_topic_enum": "EXPLICIT_INSTRUCTIONS"}},
        {"managed_memory_topic": {"managed_topic_enum": "KEY_CONVERSATION_DETAILS"}},
    ]}],
    "ttl_config": {"default_ttl": f"{30 * 24 * 3600}s"},
}
if os.environ.get("MB_CONFIG", "custom") == "default":
    memory_bank_config = {}

with open(os.path.join(HERE, "requirements-runtime.txt")) as f:
    requirements = [line.strip() for line in f if line.strip()]

config = {
    "display_name": AGENT_PKG.replace("_", "-") + "-agent",  # media_insights -> media-insights-agent
    "description": root_agent.description,
    "staging_bucket": f"gs://{os.environ['BUCKET']}",
    "requirements": requirements,
    "extra_packages": [AGENT_PKG],
    "env_vars": env_vars,
    "service_account": os.environ["AGENT_SA"],
    "min_instances": int(os.environ.get("MIN_INSTANCES", "0")),
    "max_instances": 2,
    "resource_limits": {"cpu": "1", "memory": "2Gi"},
    "context_spec": {"memory_bank_config": memory_bank_config},
}

client = vertexai.Client(project=PROJECT, location=REGION)
app = agent_engines.AdkApp(agent=root_agent)
existing = os.environ.get("AGENT_ENGINE", "")
if existing.startswith("projects/"):
    remote = client.agent_engines.update(name=existing, agent=app, config=config)
else:
    remote = client.agent_engines.create(agent=app, config=config)
print("RESOURCE_NAME=" + remote.api_resource.name)
