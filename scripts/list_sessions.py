"""List a user's sessions through whichever backend SESSION_BACKEND selects.

Usage: uv run python scripts/list_sessions.py USER_ID [--events]
Works for in_memory (only within one process), sqlite, postgres, cloud_sql and agent_platform.
"""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()  # the repo's .env; variables already set in the shell win


async def main(user_id: str, show_events: bool) -> None:
    from app.app_utils.services import get_session_service, session_service_uri

    svc = get_session_service()
    print(f"backend: {session_service_uri().split('://')[0]}")
    res = await svc.list_sessions(app_name="app", user_id=user_id)
    for s in res.sessions:
        full = await svc.get_session(app_name="app", user_id=user_id, session_id=s.id)
        print(f"- {s.id} events={len(full.events)} state={full.state}")
        if show_events:
            for i, e in enumerate(full.events):
                text = "".join(
                    p.text or ""
                    for p in (e.content.parts if e.content else []) or []
                    if getattr(p, "text", None)
                )
                print(f"    {i:>2} {e.author:<22} {text[:70]!r}")
    print(f"{len(res.sessions)} sessions")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    asyncio.run(main(sys.argv[1], "--events" in sys.argv))
