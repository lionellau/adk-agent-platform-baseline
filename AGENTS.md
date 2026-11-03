# Coding Agent Guide

## This project (read first)

mc-platform is a baseline agent platform: `media_insights` coordinator with
specialists, governed BigQuery access through the remote MCP server, an Apigee
gateway, Model Armor guardrails, sessions, Memory Bank, skills and evals. The
README has the feature map; the runbook has the cloud setup.

Rules for changes here:
- **Configuration lives in `app/config.py` and `.env`.** Add a switch there (and to
  `.env.example` and `scripts/check_env.py`), never read `os.environ` in agent code.
- **Cross-cutting controls are App plugins** (`app/plugins/`), not per-agent callbacks,
  so every agent, sub-agent and AgentTool is covered.
- **Trusted identity comes from state the application writes** (`user:business_unit`,
  `user:display_name` in `app/app_utils/chat_routes.py`). The model never sets it.
- **Sessions and memory are chosen by URI** in `app/app_utils/services.py`; add a
  backend there and a row to the parametrized test.
- **Never enable APIs, grant IAM roles or create billing-relevant resources from code
  or the CLI on the user's behalf.** Those steps are console-only in the runbook.
- **Tests first:** `uv run pytest tests/unit` runs offline against a mock model
  (`tests/unit/conftest.py`). Keep it green; live tests are opt-in
  (`RUN_LIVE_TESTS=1`, `RUN_LIVE_EVALS=1`, `PG_TEST_URL`).
- Lint with `agents-cli lint` (ruff, format, codespell and ty must all pass).

## Prerequisites

Install the CLI (one-time):
```bash
uv tool install google-agents-cli
```

---

## Development Phases

### Phase 1: Understand Requirements
Before writing any code, understand the project's requirements, constraints, and success criteria.

### Phase 2: Build and Implement
Implement agent logic in `app/`. Use `agents-cli playground` for interactive testing. Iterate based on user feedback.

### Phase 3: The Evaluation Loop (Main Iteration Phase)
Start with 1-2 eval cases, run `agents-cli eval run`, iterate by making changes and rerunning it until satisfied. Expect 5-10+ iterations. Once you have a baseline, reach for `agents-cli eval compare` (regression diffs), `agents-cli eval analyze` (cluster failure modes), and `agents-cli eval optimize` (auto-tune prompts). See the **Evaluation Guide** for metrics, dataset schema, LLM-as-judge config, and common gotchas.

### Phase 4: Pre-Deployment Tests
Run `uv run pytest tests/unit tests/integration`. Fix issues until all tests pass.

### Phase 5: Deploy to Dev
**Requires explicit human approval.** Run `agents-cli deploy` only after user confirms. See the **Deployment Guide** for details.

### Phase 6: Production Deployment
Ask the user: Option A (simple single-project) or Option B (full CI/CD pipeline with `agents-cli infra cicd`).

## Development Commands

| Command | Purpose |
|---------|---------|
| `agents-cli playground` | Interactive local testing |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests |
| `agents-cli eval dataset synthesize` | Synthesize multi-turn eval scenarios for your agent |
| `agents-cli eval run` | Run the agent over the eval dataset and grade the traces |
| `agents-cli eval generate` / `agents-cli eval grade` | Decoupled form: produce traces, then grade them |
| `agents-cli eval compare` | Compare two grade-results files (regression check) |
| `agents-cli eval analyze` | Cluster failure modes from grade results |
| `agents-cli eval metric list` | List built-in metrics available in the SDK |
| `agents-cli eval optimize` | Auto-tune agent prompts using eval data |
| `agents-cli lint` | Check code quality |
| `agents-cli infra single-project` | Set up project infrastructure (Terraform) |
| `agents-cli deploy` | Deploy to dev |
| `agents-cli scaffold enhance` | Add deployment target or CI/CD to project |
| `agents-cli scaffold upgrade` | Upgrade project to latest version |

---

## Operational Guidelines for Coding Agents

- **Code preservation**: Only modify code directly targeted by the user's request. Preserve all surrounding code, config values (e.g., `model`), comments, and formatting.
- **NEVER change the model** unless explicitly asked.
- **Model 404 errors**: Fix `GOOGLE_CLOUD_LOCATION` (e.g., `global` instead of `us-central1`), not the model name.
- **ADK tool imports**: Import the tool instance, not the module: `from google.adk.tools.load_web_page import load_web_page`
- **Run Python with `uv`**: `uv run python script.py`. Run `agents-cli install` first.
- **Stop on repeated errors**: If the same error appears 3+ times, fix the root cause instead of retrying.
- **Terraform conflicts** (Error 409): Use `terraform import` instead of retrying creation.
