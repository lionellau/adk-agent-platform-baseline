"""Usage: python3 query_remote.py USER_ID BUSINESS_UNIT "prompt 1" ["prompt 2" ...]  (one new session)."""
import asyncio
import os
import sys

import vertexai

client = vertexai.Client(project=os.environ["PROJECT_ID"], location=os.environ["REGION"])
remote = client.agent_engines.get(name=os.environ["AGENT_ENGINE"])


async def ask(user_id: str, session_id: str, text: str) -> str:
    answer = ""
    async for event in remote.async_stream_query(user_id=user_id, session_id=session_id, message=text):
        for part in (event.get("content") or {}).get("parts", []):
            if part.get("function_call"):
                print(f"   tool -> {part['function_call'].get('name')}")
            if part.get("text"):
                answer = part["text"]
    return answer


async def main() -> None:
    user_id, bu, prompts = sys.argv[1], sys.argv[2], sys.argv[3:]
    session = await remote.async_create_session(user_id=user_id, state={"business_unit": bu})
    print(f"session {session['id']} (user {user_id}, bu {bu})")
    for text in prompts:
        print(f">> {text}")
        print(f"<< {await ask(user_id, session['id'], text)}\n")


asyncio.run(main())
