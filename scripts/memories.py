"""R5: list Memory Bank memories, or delete one user's memories ("right to be forgotten").

Usage:
  python3 scripts/memories.py list                     # read-only
  python3 scripts/memories.py forget USER_ID           # dry run: shows what would be deleted
  CONFIRM=USER_ID python3 scripts/memories.py forget USER_ID   # deletes them
Needs PROJECT_ID, REGION and AGENT_ENGINE in the environment (source ~/platform.env).
"""
import os
import sys

import vertexai

client = vertexai.Client(project=os.environ["PROJECT_ID"], location=os.environ["REGION"])
engine = os.environ["AGENT_ENGINE"]
action = sys.argv[1] if len(sys.argv) > 1 else "list"
memories = list(client.agent_engines.memories.list(name=engine))

if action == "list":
    for m in memories:
        print("-", m.scope, "|", m.fact)
    print(f"{len(memories)} memories")
elif action == "forget" and len(sys.argv) == 3:
    user = sys.argv[2]
    hits = [m for m in memories if (m.scope or {}).get("user_id") == user]
    for m in hits:
        print("match:", m.name.split("/")[-1], "|", m.fact)
    if os.environ.get("CONFIRM") != user:
        print(f"dry run: {len(hits)} memories for {user}. To delete them, re-run with CONFIRM={user}")
    else:
        for m in hits:
            client.agent_engines.memories.delete(name=m.name)
            print("deleted", m.name)
else:
    sys.exit(__doc__)
