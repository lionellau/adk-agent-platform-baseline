"""Check .env before running anything: no placeholders, required values present, choices valid.

Usage: uv run python scripts/check_env.py
"""

from __future__ import annotations

import sys

from dotenv import dotenv_values

REQUIRED = [
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "REGION",
    "MODEL",
    "BQ_DATASET",
]
CHOICES = {
    "SESSION_BACKEND": {
        "auto",
        "in_memory",
        "sqlite",
        "postgres",
        "cloud_sql",
        "agent_platform",
    },
    "MEMORY_BACKEND": {"auto", "in_memory", "agent_platform", "none"},
    "MEMORY_MODE": {"preload", "tool", "both"},
}


def main() -> int:
    env = {k: v or "" for k, v in dotenv_values(".env").items()}
    problems = []
    for k, v in env.items():
        if "FILL_IN" in v or "REPLACE_ME" in v or v.startswith("your-"):
            problems.append(f"{k} still has a placeholder: {v}")
    for k in REQUIRED:
        if not env.get(k):
            problems.append(f"{k} is empty")
    for k, allowed in CHOICES.items():
        if env.get(k) and env[k] not in allowed:
            problems.append(f"{k}={env[k]} is not one of {sorted(allowed)}")
    if env.get("SESSION_BACKEND") == "postgres" and not env.get(
        "DATABASE_URL", ""
    ).startswith("postgresql"):
        problems.append(
            "SESSION_BACKEND=postgres needs DATABASE_URL=postgresql+asyncpg://..."
        )
    if (
        env.get("SESSION_BACKEND") == "agent_platform"
        or env.get("MEMORY_BACKEND") == "agent_platform"
    ):
        if not env.get("AGENT_ENGINE"):
            problems.append(
                "agent_platform backends need AGENT_ENGINE (scripts/setup_agent_runtime_backend.py)"
            )
    if env.get("SESSION_BACKEND") == "cloud_sql" and not env.get(
        "INSTANCE_CONNECTION_NAME"
    ):
        problems.append("SESSION_BACKEND=cloud_sql needs INSTANCE_CONNECTION_NAME")
    if env.get("USE_APIGEE", "false").lower() == "true":
        for k in ("APIGEE_PROXY_URL", "APIGEE_KEY_SECRET"):
            if not env.get(k):
                problems.append(f"USE_APIGEE=true needs {k}")
    for p in problems:
        print("FIX:", p)
    print(".env OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
