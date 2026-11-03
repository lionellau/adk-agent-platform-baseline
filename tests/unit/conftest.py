"""Offline test harness: a local mock of the Gemini API, fake credentials, in-memory services.

No Google Cloud project is needed. Model calls go through the Apigee code path
(USE_APIGEE=true) to a local HTTP server that imitates generateContent and
streamGenerateContent, so the real ADK runner, plugins, sessions and memory run.

Mock behaviour: if the latest user text contains "remember" and the model has not
called a tool yet, it returns a remember_preference function call; otherwise it
answers "MOCK ANSWER: <user text>".
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REQUESTS: list[dict] = []


def _latest_user_text(body: dict) -> str:
    for content in reversed(body.get("contents", [])):
        if content.get("role") == "user":
            for part in content.get("parts", []):
                if "text" in part:
                    return part["text"]
    return ""


def _already_called_tool(body: dict) -> bool:
    last = (body.get("contents") or [{}])[-1]
    return any("functionResponse" in p for p in last.get("parts", []))


def _reply(body: dict) -> dict:
    text = _latest_user_text(body)
    if "remember" in text.lower() and not _already_called_tool(body):
        part = {
            "functionCall": {
                "name": "remember_preference",
                "args": {"preference": "Prefers answers as at most 3 bullet points."},
            }
        }
    else:
        part = {"text": f"MOCK ANSWER: {text[:80]}"}
    return {
        "candidates": [
            {"content": {"role": "model", "parts": [part]}, "finishReason": "STOP"}
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 5,
            "totalTokenCount": 15,
        },
        "modelVersion": "mock",
    }


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(
            self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}"
        )
        REQUESTS.append(
            {"path": self.path, "apikey": self.headers.get("x-apikey"), "body": body}
        )
        reply = _reply(body)
        if "streamGenerateContent" in self.path:
            data = f"data: {json.dumps(reply)}\n\n".encode()
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
        else:
            data = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


_server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
threading.Thread(target=_server.serve_forever, daemon=True).start()

# Environment must be set before any app module is imported (settings are read once).
os.environ.update(
    {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GOOGLE_CLOUD_LOCATION": "global",
        "GOOGLE_GENAI_USE_ENTERPRISE": "true",
        "USE_APIGEE": "true",
        "APIGEE_PROXY_URL": f"http://127.0.0.1:{_server.server_address[1]}/llm",
        "APIGEE_KEY_SECRET": "",
        "MA_TEMPLATE": "",
        "SESSION_BACKEND": "in_memory",
        "MEMORY_BACKEND": "in_memory",
        "MEMORY_MODE": "both",
        "BQ_ANALYTICS": "false",
        "EXAMPLE_STORE_NAME": "",
        "SANDBOX_RESOURCE_NAME": "",
    }
)
for key in ("AGENT_ENGINE", "GOOGLE_CLOUD_AGENT_ENGINE_ID", "SESSION_SERVICE_URI"):
    os.environ.pop(key, None)

import google.auth  # noqa: E402
import google.auth.credentials  # noqa: E402


class _FakeCredentials(google.auth.credentials.Credentials):
    def __init__(self):
        super().__init__()
        self.token = "fake-token"

    def refresh(self, request):
        self.token = "fake-token"

    @property
    def valid(self):
        return True


google.auth.default = lambda *args, **kwargs: (_FakeCredentials(), "test-project")
