"""Memory tools (Course 6 ch. 3 and the ch2 memory lab).

Two retrieval styles, chosen by MEMORY_MODE:
- proactive: ``PreloadMemoryTool`` searches memory before every model call;
- reactive: the ADK ``load_memory`` tool, which the agent calls when it decides to.

One generation style the agent controls ("memory as a tool"): ``remember_preference``
writes a fact the agent has already extracted to user-scoped state (instant, every
session of that user) and to Memory Bank (long-term; Memory Bank only consolidates it).
Whole sessions are also sent to memory after each turn by MemoryPlugin.
"""

from __future__ import annotations

from google.adk.memory.memory_entry import MemoryEntry
from google.adk.tools import ToolContext, load_memory
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from app.config import settings

MAX_PREFERENCES = 10


async def remember_preference(preference: str, tool_context: ToolContext) -> dict:
    """Saves one lasting preference or instruction the user stated about themselves.

    Call it only when the user explicitly asks you to remember something, or states a
    lasting preference (answer format, length, language, business focus). Do not call
    it for one-off questions or for facts about content.

    Args:
        preference: The preference in one short third-person sentence, for example
            "Prefers answers as at most 3 bullet points."

    Returns:
        dict: {"status": "saved", "stored_in": [...]} or {"status": "error", "message": str}.
    """
    stored_in = []
    # 1) User-scoped state: every later session of this user sees it at once ({user:preferences?}).
    prefs = [
        p for p in tool_context.state.get("user:preferences", []) if p != preference
    ]
    tool_context.state["user:preferences"] = [*prefs, preference][-MAX_PREFERENCES:]
    stored_in.append("user_state")
    # 2) Memory Bank: long-term, consolidated with what it already knows about the user.
    try:
        await tool_context.add_memory(
            memories=[
                MemoryEntry(
                    content=types.Content(
                        role="user", parts=[types.Part(text=preference)]
                    )
                )
            ],
            custom_metadata={"source": "remember_preference"},
        )
        stored_in.append("memory_service")
    except NotImplementedError:
        pass  # the in-memory dev service has no direct writes; Memory Bank does
    except Exception as exc:  # memory must never break the answer
        return {
            "status": "error",
            "message": f"could not save to memory: {exc!r}"[:200],
            "stored_in": stored_in,
        }
    return {"status": "saved", "stored_in": stored_in}


def memory_tools(memory_enabled: bool) -> list:
    """The memory tools for the root agent, given MEMORY_MODE and whether a service exists."""
    if not memory_enabled:
        return []
    tools: list = [remember_preference]
    if settings.memory_mode in ("preload", "both"):
        tools.append(PreloadMemoryTool())
    if settings.memory_mode in ("tool", "both"):
        tools.append(load_memory)
    return tools
