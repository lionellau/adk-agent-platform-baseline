"""Sends the session to the memory service after each turn (the ch2 memory lab pattern).

On Memory Bank this starts asynchronous LLM extraction and consolidation, limited by
the bank's topics (see scripts/setup_agent_runtime_backend.py). A memory failure is
logged and never breaks the answer.
"""

from __future__ import annotations

import json
import logging

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin

log = logging.getLogger("app.memory")


class MemoryPlugin(BasePlugin):
    def __init__(self, enabled: bool = True):
        super().__init__(name="save_session_to_memory")
        self.enabled = enabled

    async def after_run_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        memory = invocation_context.memory_service
        if not (self.enabled and memory and invocation_context.session):
            return
        try:
            await memory.add_session_to_memory(invocation_context.session)
        except Exception as exc:
            log.warning(
                json.dumps({"event": "memory_error", "detail": repr(exc)[:200]})
            )
