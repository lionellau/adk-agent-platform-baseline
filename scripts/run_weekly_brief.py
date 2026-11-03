"""Run the weekly brief graph workflow once, as a batch job (no chat, no user).

Usage: uv run python -m scripts.run_weekly_brief --business-unit news [--out brief.md]

Uses the same guardrail plugin as the chat app and the session backend from .env,
so a job run is auditable like a chat turn. Schedule it with Cloud Scheduler +
Cloud Run jobs when needed; in the sandbox run it by hand.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from google.genai import types

APP_NAME = "weekly_brief_job"
BUSINESS_UNITS = ("news", "entertainment", "legal", "platform")


async def run(business_unit: str) -> dict:
    from google.adk.runners import Runner

    from app.app_utils import services
    from app.config import settings
    from app.plugins.guardrails import ModelArmorGuardrailPlugin
    from app.workflows.weekly_brief_graph import weekly_brief_graph

    sessions = services.get_session_service()
    runner = Runner(
        app_name=APP_NAME,
        node=weekly_brief_graph(),
        session_service=sessions,
        plugins=[
            ModelArmorGuardrailPlugin(
                template_name=settings.model_armor_template_name,
                fail_open=settings.guardrail_fail_open,
                max_llm_calls=settings.max_llm_calls,
            )
        ],
    )
    session = await sessions.create_session(
        app_name=APP_NAME,
        user_id="scheduler",
        state={"user:business_unit": business_unit},
    )
    published: dict = {}
    async for event in runner.run_async(
        user_id="scheduler",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=f"Weekly brief for {business_unit}")],
        ),
    ):
        output = getattr(event, "output", None)
        if isinstance(output, dict) and "brief" in output:
            published = output
    return {"session_id": session.id, **published}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-unit", choices=BUSINESS_UNITS, default="news")
    parser.add_argument("--out", help="Also write the brief to this file.")
    args = parser.parse_args()
    result = asyncio.run(run(args.business_unit))
    if not result.get("brief"):
        print("FIX: the workflow produced no brief", json.dumps(result)[:500])
        return 1
    print(result["brief"])
    print(f"\n[session {result['session_id']}, {result['chars']} chars]")
    if args.out:
        with open(args.out, "w") as f:
            f.write(result["brief"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
