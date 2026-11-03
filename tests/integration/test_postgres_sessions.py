"""Sessions on a real Postgres (SESSION_BACKEND=postgres). Skipped unless PG_TEST_URL is set.

Run locally:
  export POSTGRES_PASSWORD=$(openssl rand -hex 12)
  docker compose -f deployment/postgres/docker-compose.yml up -d --wait
  PG_TEST_URL=postgresql+asyncpg://adk:$POSTGRES_PASSWORD@localhost:5432/adk_sessions uv run pytest tests/integration/test_postgres_sessions.py
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

PG_URL = os.environ.get("PG_TEST_URL", "")
pytestmark = pytest.mark.skipif(not PG_URL, reason="PG_TEST_URL not set")


def test_sessions_persist_across_service_instances():
    from google.adk.cli.utils.service_factory import create_session_service_from_options
    from google.adk.events import Event, EventActions

    user = f"pg-{uuid.uuid4().hex[:8]}"

    async def run():
        first = create_session_service_from_options(
            base_dir=".", session_service_uri=PG_URL
        )
        s = await first.create_session(
            app_name="app",
            user_id=user,
            state={"user:business_unit": "news", "draft": 1},
        )
        await first.append_event(
            s,
            Event(
                author="system",
                invocation_id="i1",
                actions=EventActions(state_delta={"step": "done"}),
            ),
        )
        # A new service instance is what a restarted server or another replica sees.
        second = create_session_service_from_options(
            base_dir=".", session_service_uri=PG_URL
        )
        restored = await second.get_session(
            app_name="app", user_id=user, session_id=s.id
        )
        next_session = await second.create_session(app_name="app", user_id=user)
        listed = await second.list_sessions(app_name="app", user_id=user)
        for sess in listed.sessions:
            await second.delete_session(
                app_name="app", user_id=user, session_id=sess.id
            )
        return restored, next_session, listed

    restored, next_session, listed = asyncio.run(run())
    assert restored.state["step"] == "done" and restored.state["draft"] == 1
    assert len(restored.events) == 1
    assert (
        next_session.state["user:business_unit"] == "news"
    )  # user scope survives in the database
    assert len(listed.sessions) == 2
