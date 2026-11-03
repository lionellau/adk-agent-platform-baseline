"""Google's managed BigQuery MCP server as an ADK toolset (read-only tools only).

Design call path 3: Google-managed MCP servers are called directly under IAM, without
an Apigee hop. Two independent layers keep it read-only: ``tool_filter`` exposes no
write tool, and the agent's identity has read access to one dataset only.
"""

from __future__ import annotations

import google.auth
import google.auth.transport.requests
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from app.config import settings

BIGQUERY_MCP_URL = "https://bigquery.googleapis.com/mcp"
READ_ONLY_TOOLS = ["list_table_ids", "get_table_info", "execute_sql_readonly"]

_creds = None


def _auth_headers(_ctx) -> dict[str, str]:
    """A fresh OAuth token per call: tokens expire after about an hour on a long-lived server."""
    global _creds
    if _creds is None:
        _creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    if not _creds.valid:
        _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "x-goog-user-project": settings.project,
    }


def bigquery_toolset() -> McpToolset:
    """A new toolset instance per agent (toolsets hold their own MCP session).

    Defined synchronously at import time: an async factory works in `adk web` but
    fails on Cloud Run, GKE and Agent Runtime (Course 4 deployment rule).
    """
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=BIGQUERY_MCP_URL, timeout=30
        ),
        tool_filter=READ_ONLY_TOOLS,
        header_provider=_auth_headers,
    )


def dataset_hint() -> str:
    """Instruction text naming the dataset and tables, so the model never guesses schema."""
    ds = f"{settings.project}.{settings.bq_dataset}"
    return (
        f"BigQuery dataset `{ds}` has two tables:\n"
        f"- `{ds}.content_catalogue` (content_id, title, business_unit, genre, language, release_date, duration_min)\n"
        f"- `{ds}.daily_viewership` (view_date, content_id, platform, views, watch_minutes)\n"
        f"Use execute_sql_readonly with fully qualified table names, and always set projectId to "
        f'"{settings.project}". Use get_table_info only if a query fails because of a column name.'
    )
