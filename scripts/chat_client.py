"""Command-line client for the platform's chat API (the "custom app" stand-in).

Creates one session with the trusted business unit in state, sends each prompt in
that session (so later prompts can say "it"), and prints tool calls, transfers and
the final answer from the SSE stream.

Usage (repo root):
  uv run python scripts/chat_client.py --url http://localhost:8080 --user u-anna --bu entertainment \\
      "Which title had the most total views in October 2026?" "Can we stream it in Malaysia?"

--url is the server's base URL:
  local server      http://localhost:8080
  Agent Runtime     https://REGION-aiplatform.googleapis.com/reasoningEngines/v1/<engine>/api
  Cloud Run         https://<service>-<hash>.<region>.run.app
Auth is chosen from the URL (--auth auto): none for localhost, a Google access token
for Agent Runtime, an identity token for Cloud Run. Tokens come from gcloud.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import requests


def _token(kind: str, url: str) -> str | None:
    if kind == "auto":
        if "aiplatform.googleapis.com" in url:
            kind = "access"
        elif ".run.app" in url:
            kind = "identity"
        else:
            kind = "none"
    if kind == "none":
        return None
    cmd = ["gcloud", "auth", f"print-{kind}-token"]
    return subprocess.run(
        cmd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _events(resp: requests.Response):
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            yield json.loads(line[6:])


def chat(
    base: str, user: str, bu: str, prompts: list[str], auth: str = "auto"
) -> list[str]:
    base = base.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if token := _token(auth, base):
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(
        f"{base}/api/sessions",
        headers=headers,
        json={"user_id": user, "business_unit": bu},
        timeout=120,
    )
    r.raise_for_status()
    session_id = r.json()["session"]["session_id"]
    print(f"session {session_id} user={user} business_unit={bu}")
    answers = []
    for prompt in prompts:
        print(f"\n> {prompt}")
        with requests.post(
            f"{base}/api/chat",
            headers=headers,
            json={"user_id": user, "session_id": session_id, "message": prompt},
            stream=True,
            timeout=300,
        ) as resp:
            resp.raise_for_status()
            final = ""
            for ev in _events(resp):
                if ev["type"] == "tool_call":
                    print(f"  tool -> {', '.join(ev['names'])} ({ev['author']})")
                elif ev["type"] == "transfer":
                    print(f"  transfer -> {ev['to']}")
                elif ev["type"] == "error":
                    print(f"  ERROR {ev['message']}")
                elif ev["type"] == "final":
                    final = ev.get("text", "")
            print(final)
            answers.append(final)
    return answers


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--url", default="http://localhost:8080")
    p.add_argument("--user", required=True)
    p.add_argument(
        "--bu", default="news", choices=["news", "entertainment", "legal", "platform"]
    )
    p.add_argument(
        "--auth", default="auto", choices=["auto", "none", "access", "identity"]
    )
    p.add_argument("prompts", nargs="+")
    a = p.parse_args()
    chat(a.url, a.user, a.bu, a.prompts, a.auth)
    return 0


if __name__ == "__main__":
    sys.exit(main())
