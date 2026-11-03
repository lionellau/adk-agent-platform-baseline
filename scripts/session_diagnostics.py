"""Time each phase of an Agent Platform Sessions cold start (the ch2 lab's diagnostics).

Compare step 4 (first list) with step 5 (second list on the same instance):
- if step 5 drops to the warm baseline, the cold cost is connection set-up (TLS + HTTP/2),
  which the server's start-up warm-up removes;
- if step 5 is still slow, the cost is per request (server side), and warm-up won't help.

Usage: SESSION_BACKEND=agent_platform AGENT_ENGINE=... uv run python scripts/session_diagnostics.py
"""

from __future__ import annotations

import asyncio
import time

from dotenv import load_dotenv

load_dotenv()  # the repo's .env; variables already set in the shell win


def _ms(t: float) -> str:
    return f"{(time.perf_counter() - t) * 1000:.0f} ms"


async def main() -> None:
    t = time.perf_counter()
    import google.auth
    from google.auth.transport.requests import Request

    from app.app_utils.services import get_session_service

    print("1. imports:", _ms(t))
    t = time.perf_counter()
    creds, _ = google.auth.default()
    creds.refresh(Request())
    print("2. credentials + token:", _ms(t))
    t = time.perf_counter()
    svc = get_session_service()
    print("3. construct session service:", _ms(t))
    t = time.perf_counter()
    await svc.list_sessions(app_name="app", user_id="_diag")
    print("4. first list_sessions:", _ms(t))
    t = time.perf_counter()
    await svc.list_sessions(app_name="app", user_id="_diag")
    print("5. second list_sessions (same instance):", _ms(t))
    t = time.perf_counter()
    s = await svc.create_session(app_name="app", user_id="_diag", state={})
    print("6. create_session:", _ms(t))
    await svc.delete_session(app_name="app", user_id="_diag", session_id=s.id)


if __name__ == "__main__":
    asyncio.run(main())
