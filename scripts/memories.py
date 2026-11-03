"""Inspect and manage Memory Bank memories (Course 6 ch. 3; the "right to be forgotten").

Usage (repo root; AGENT_ENGINE and GOOGLE_CLOUD_PROJECT set):
  uv run python scripts/memories.py list                         # all memories on the engine
  uv run python scripts/memories.py search u-ben "answer format"  # similarity search for one user
  uv run python scripts/memories.py profile u-ben                 # structured user profile
  uv run python scripts/memories.py forget u-ben                  # dry run: what would be deleted
  CONFIRM=u-ben uv run python scripts/memories.py forget u-ben    # delete that user's memories

Scope: ADK writes memories with scope {"app_name": "app", "user_id": <user>}.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()  # the repo's .env; variables already set in the shell win

APP_NAME = os.environ.get("APP_NAME", "app")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in {"list", "search", "profile", "forget"}:
        print(__doc__)
        return 2
    import agentplatform

    from app.app_utils.services import (
        agent_engine_resource_name,
        agent_runtime_location,
    )

    engine = agent_engine_resource_name()
    if not engine:
        print(
            "FIX: set AGENT_ENGINE (scripts/setup_agent_runtime_backend.py prints it)"
        )
        return 1
    client = agentplatform.Client(
        project=os.environ["GOOGLE_CLOUD_PROJECT"], location=agent_runtime_location()
    )
    memories = client.memory_banks.memories
    action = sys.argv[1]

    if action == "list":
        n = 0
        for m in memories.list(name=engine):
            n += 1
            print(f"- {m.scope} | {m.fact}")
        print(f"{n} memories")
    elif action == "search":
        user, query = sys.argv[2], " ".join(sys.argv[3:]) or "preferences"
        res = memories.retrieve(
            name=engine,
            scope={"app_name": APP_NAME, "user_id": user},
            similarity_search_params={"search_query": query, "top_k": 5},
        )
        for r in res:
            print(f"- distance={getattr(r, 'distance', None)} | {r.memory.fact}")
    elif action == "profile":
        user = sys.argv[2]
        res = memories.retrieve_profiles(
            name=engine, scope={"app_name": APP_NAME, "user_id": user}
        )
        print(res)
    elif action == "forget":
        user = sys.argv[2]
        hits = [
            m
            for m in memories.list(name=engine)
            if (m.scope or {}).get("user_id") == user
        ]
        for m in hits:
            print(f"match: {m.name.split('/')[-1]} | {m.fact}")
        if os.environ.get("CONFIRM") != user:
            print(
                f"dry run: {len(hits)} memories for {user}. To delete, re-run with CONFIRM={user}"
            )
        else:
            for m in hits:
                memories.delete(name=m.name)
                print(f"deleted {m.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
