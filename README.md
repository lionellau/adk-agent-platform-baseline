# mc-platform

A baseline agent platform on Google Cloud, built on the official
[agents-cli](https://github.com/google/agents-cli) `adk_python` template
(agents-cli 1.12.0, ADK 2.13). It shows, in one small project, the patterns a
production agent platform needs: multi-agent routing, governed data access through
the BigQuery remote MCP server, an Apigee gateway, Model Armor guardrails, sessions
on several backends, Memory Bank, skills, few-shot examples, a streaming API with a
browser client, A2A, evaluation and deployment to Agent Runtime or Cloud Run.

The step-by-step sandbox setup (prerequisites, console steps for high-risk actions,
tests and demos) lives in a separate runbook. This README is the map.

## The agent

```
media_insights (coordinator, LlmAgent)                       app/agent.py
├── analytics_agent        sub-agent: BigQuery MCP, read-only  app/agents/specialists.py
├── rights_agent           sub-agent: content API via Apigee    app/agents/specialists.py
├── weekly_brief_pipeline  AgentTool: Sequential -> Loop(writer, reviewer)  app/agents/weekly_brief.py
├── report_writer          AgentTool: skills (inline, file, meta)          app/skills_toolset.py
├── chart_analyst          AgentTool, optional: code execution sandbox
├── memory tools           remember_preference, PreloadMemoryTool, load_memory  app/tools/memory_tools.py
└── ExampleTool            optional: Example Store few-shot
App plugins: guardrails (Model Armor + call cap), Apigee key, memory, context filter,
event compaction, context cache, optional BigQuery agent analytics.
```

`app/workflows/weekly_brief_graph.py` is the same brief as an ADK 2.0 graph
`Workflow`, run as a batch job by `scripts/run_weekly_brief.py`.

## Feature map

| Feature | Where | Switch |
|---|---|---|
| Model via Agent Platform or Apigee | `app/models.py`, `app/plugins/apigee.py` | `USE_APIGEE` |
| BigQuery remote MCP (read-only tools) | `app/tools/bigquery.py` | `BQ_DATASET` |
| Content rights API with state-based access check | `app/tools/content_api.py` | `CONTENT_API_URL` |
| Model Armor input/output screening, fail closed, call cap | `app/plugins/guardrails.py` | `MA_TEMPLATE`, `GUARDRAIL_FAIL_OPEN`, `MAX_LLM_CALLS` |
| Sessions: in-memory, SQLite, Postgres, Cloud SQL, Agent Platform | `app/app_utils/services.py` | `SESSION_BACKEND` |
| Memory Bank (topics, custom topic + examples, profile, TTL) | `scripts/setup_agent_runtime_backend.py` | `MEMORY_BACKEND`, `AGENT_ENGINE` |
| Memory recall: proactive, reactive or both | `app/tools/memory_tools.py` | `MEMORY_MODE` |
| Memory generation: per turn and memory-as-a-tool | `app/plugins/memory.py`, `remember_preference` | `SAVE_MEMORY_EACH_TURN` |
| State scopes `user:` / `app:` / `temp:` | `app/agent.py`, `app/app_utils/chat_routes.py` | |
| Context: sliding window, compaction, caching | `app/agent.py` | `KEEP_LAST_INVOCATIONS`, `COMPACTION_INTERVAL`, `CONTEXT_CACHE` |
| Skills (inline, file-based, meta) and Skills Registry | `app/skills*`, `scripts/publish_skill.py` | |
| Example Store few-shot | `scripts/example_store.py` | `EXAMPLE_STORE_NAME` |
| Code execution sandbox | `scripts/create_sandbox.py` | `SANDBOX_RESOURCE_NAME` |
| Streaming chat API + session cards + browser client | `app/app_utils/chat_routes.py`, `app/static/client.html` | |
| A2A agent card and JSON-RPC | `app/app_utils/a2a.py` (template) | |
| Evals: agents-cli metrics, ADK evalsets, multi-turn synthesis | `tests/eval/` | |
| Platform IaC: dataset, Model Armor, key secrets, IAM | `deployment/terraform/platform/` | |
| Deployment IaC + CI/CD (template) | `deployment/terraform*/`, `.github/workflows/` | |

## Quick start

Offline (no Google Cloud project; a local mock stands in for Gemini):

```bash
uv sync --extra eval
uv run pytest tests/unit
```

With a sandbox project (after the runbook's prerequisites):

```bash
cp .env.example .env        # or paste the runbook's .env block, then edit
uv run python scripts/check_env.py
agents-cli playground       # ADK dev UI
uv run uvicorn app.fast_api_app:app --port 8000   # API + /client
```

## Tests

| Command | Needs |
|---|---|
| `uv run pytest tests/unit` | nothing (mock model) |
| `PG_TEST_URL=postgresql+asyncpg://... uv run pytest tests/integration/test_postgres_sessions.py` | local Postgres (`deployment/postgres`) |
| `RUN_LIVE_TESTS=1 uv run pytest tests/integration` | ADC + project |
| `RUN_LIVE_EVALS=1 uv run --extra eval pytest tests/integration/test_adk_evalsets.py` | ADC + project + data |
| `agents-cli eval run` | ADC + project + data |

## Deploy

```bash
agents-cli deploy -d agent_runtime     # managed sessions + Memory Bank on the same engine
agents-cli deploy -d cloud_run         # container; sessions in Cloud SQL or Agent Platform
```

`agents-cli infra single-project` and `agents-cli infra cicd` apply the template's
Terraform. Both enable APIs and grant IAM roles: review `terraform plan` first.

## Credits

Generated with `agents-cli` 1.12.0 (Apache 2.0, Google LLC). Files changed from the
template keep Google's header and say what was modified.
