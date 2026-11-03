"""R4: list the managed Sessions stored for the deployed agent (read-only).

Needs PROJECT_ID, REGION and AGENT_ENGINE in the environment (source ~/platform.env).
"""
import os

import vertexai

client = vertexai.Client(project=os.environ["PROJECT_ID"], location=os.environ["REGION"])
for s in client.agent_engines.sessions.list(name=os.environ["AGENT_ENGINE"]):
    print(s.name.split("/")[-1], s.user_id, s.session_state)
