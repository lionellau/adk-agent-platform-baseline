"""Custom-app API for the agent (design scenario B), following the ch2 sessions lab.

Endpoints (mounted under /api by fast_api_app):
  POST   /api/sessions                      create a session; the APP sets trusted state
  GET    /api/sessions/{user_id}            list a user's sessions
  GET    /api/sessions/{user_id}/{sid}      session card: state + event summaries
  DELETE /api/sessions/{user_id}/{sid}      delete a session
  POST   /api/chat                          stream an answer (SSE) with session cards
  GET    /api/memories/{user_id}?q=...      what memory returns for this user and query
  GET    /client                            minimal browser client (static/client.html)

Trusted identity: ``user:business_unit`` and ``user:display_name`` are written here by
the application, never by the model, so tools can rely on them for access checks.
In production put this behind your sign-in (IAP or the custom app's own auth) and take
user_id from the verified identity, not from the request body.
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from pydantic import BaseModel

from app.app_utils import services
from app.config import settings

log = logging.getLogger("app.chat")
STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"
BUSINESS_UNITS = {"news", "entertainment", "legal", "platform"}


class NewSession(BaseModel):
    user_id: str
    business_unit: str = "news"
    display_name: str = ""
    initial_state: dict[str, Any] = {}


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: str | None = None


def _event_summary(event, index: int) -> dict:
    summary: dict[str, Any] = {"index": index, "author": event.author}
    if calls := event.get_function_calls():
        summary["tool_calls"] = [{"name": c.name, "args": c.args} for c in calls]
    if responses := event.get_function_responses():
        summary["tool_responses"] = [r.name for r in responses]
    if event.content and event.content.parts:
        text = "".join(
            p.text or "" for p in event.content.parts if getattr(p, "text", None)
        )
        if text:
            summary["text_preview"] = text[:120]
    if event.actions and event.actions.state_delta:
        summary["state_delta"] = list(event.actions.state_delta)
    if event.actions and event.actions.transfer_to_agent:
        summary["transfer_to"] = event.actions.transfer_to_agent
    if event.actions and event.actions.compaction:
        # A summary of older events written by EventsCompactionConfig (context management).
        summary["compaction"] = True
    return summary


def _card(session) -> dict:
    return {
        "type": "session_card",
        "session": {
            "session_id": session.id,
            "user_id": session.user_id,
            "state": session.state,
            "events_count": len(session.events),
            "last_update_time": int(session.last_update_time * 1000)
            if session.last_update_time
            else None,
        },
        "events": [_event_summary(e, i) for i, e in enumerate(session.events)],
    }


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


async def warm_up_sessions(app_name: str) -> None:
    """First call to Agent Platform Sessions pays TLS + HTTP/2 set-up; do it at start-up (ch2 lab)."""
    t = time.perf_counter()
    try:
        await services.get_session_service().list_sessions(
            app_name=app_name, user_id="_warmup"
        )
        log.info("session warm-up done in %.0f ms", (time.perf_counter() - t) * 1000)
    except Exception as exc:
        log.warning("session warm-up failed: %s", exc)


def attach_chat_routes(app: FastAPI) -> None:
    sessions = services.get_session_service

    def app_name() -> str:
        return app.state.agent_app_name

    @app.post("/api/sessions")
    async def create_session(req: NewSession):
        if req.business_unit not in BUSINESS_UNITS:
            raise HTTPException(
                400, f"business_unit must be one of {sorted(BUSINESS_UNITS)}"
            )
        state = {
            **req.initial_state,
            "user:business_unit": req.business_unit,
            "user:display_name": req.display_name or req.user_id,
        }
        session = await sessions().create_session(
            app_name=app_name(), user_id=req.user_id, state=state
        )
        return _card(session)

    @app.get("/api/sessions/{user_id}")
    async def list_sessions(user_id: str):
        res = await sessions().list_sessions(app_name=app_name(), user_id=user_id)
        return [
            {"session_id": s.id, "last_update_time": s.last_update_time}
            for s in res.sessions
        ]

    @app.get("/api/sessions/{user_id}/{session_id}")
    async def get_session(user_id: str, session_id: str):
        session = await sessions().get_session(
            app_name=app_name(), user_id=user_id, session_id=session_id
        )
        if not session:
            raise HTTPException(404, "session not found")
        return _card(session)

    @app.delete("/api/sessions/{user_id}/{session_id}")
    async def delete_session(user_id: str, session_id: str):
        await sessions().delete_session(
            app_name=app_name(), user_id=user_id, session_id=session_id
        )
        return {"deleted": session_id}

    @app.get("/api/memories/{user_id}")
    async def search_memories(user_id: str, q: str = "preferences"):
        memory = services.get_memory_service()
        if memory is None:
            return {"memories": [], "note": "MEMORY_BACKEND=none"}
        res = await memory.search_memory(app_name=app_name(), user_id=user_id, query=q)
        out = []
        for m in res.memories:
            text = "".join(
                p.text or ""
                for p in (m.content.parts or [])
                if getattr(p, "text", None)
            )
            out.append({"text": text, "author": m.author, "timestamp": m.timestamp})
        return {"memories": out}

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        runner = app.state.runner
        if req.session_id:
            session = await sessions().get_session(
                app_name=app_name(), user_id=req.user_id, session_id=req.session_id
            )
            if not session:
                raise HTTPException(
                    400,
                    f"session '{req.session_id}' not found for user '{req.user_id}'",
                )
        else:
            session = await sessions().create_session(
                app_name=app_name(), user_id=req.user_id, state={}
            )
        message = types.Content(role="user", parts=[types.Part(text=req.message)])

        async def stream():
            yield _sse(_card(session))
            final_text = ""
            try:
                async for event in runner.run_async(
                    user_id=req.user_id,
                    session_id=session.id,
                    new_message=message,
                    run_config=RunConfig(
                        streaming_mode=StreamingMode.SSE
                        if settings.stream_model_calls
                        else StreamingMode.NONE
                    ),
                ):
                    if event.get_function_calls() and not event.partial:
                        yield _sse(
                            {
                                "type": "tool_call",
                                "author": event.author,
                                "names": [c.name for c in event.get_function_calls()],
                            }
                        )
                    if event.actions and event.actions.transfer_to_agent:
                        yield _sse(
                            {"type": "transfer", "to": event.actions.transfer_to_agent}
                        )
                    text = "".join(
                        p.text or ""
                        for p in (event.content.parts if event.content else []) or []
                        if getattr(p, "text", None)
                    )
                    if text and event.partial:
                        yield _sse(
                            {
                                "type": "response_chunk",
                                "author": event.author,
                                "text": text,
                            }
                        )
                    elif text and event.is_final_response():
                        final_text = text
                updated = await sessions().get_session(
                    app_name=app_name(), user_id=req.user_id, session_id=session.id
                )
                yield _sse(_card(updated))
                yield _sse(
                    {"type": "final", "text": final_text, "session_id": session.id}
                )
            except Exception as exc:
                log.error("agent run failed: %s", exc, exc_info=True)
                yield _sse(
                    {"type": "error", "message": f"Agent execution failed: {exc}"}
                )
                yield _sse(
                    {
                        "type": "final",
                        "text": "",
                        "error": True,
                        "session_id": session.id,
                    }
                )

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/client", include_in_schema=False)
    async def client():
        return FileResponse(STATIC / "client.html")
