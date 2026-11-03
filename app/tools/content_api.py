"""Enterprise REST API behind Apigee (design call path 2), with a state-based access check.

The access check follows Course 4's ToolContext pattern: ``user:business_unit`` is
written by the application when it creates the session (see chat routes), not by the
model, so the model cannot talk its way past it.
"""

from __future__ import annotations

import functools

import requests
from google.adk.tools import ToolContext
from google.api_core.client_options import ClientOptions

from app.config import settings

# Business units allowed to read distribution rights (app policy, not model choice).
RIGHTS_READERS = {"entertainment", "legal", "platform"}


@functools.cache
def apigee_key() -> str:
    """This deployment's Apigee API key, read from Secret Manager at run time (never from code)."""
    if not (settings.apigee_key_secret and settings.project):
        return ""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient(
        client_options=ClientOptions(quota_project_id=settings.project)
    )
    name = f"projects/{settings.project}/secrets/{settings.apigee_key_secret}/versions/latest"
    return client.access_secret_version(name=name).payload.data.decode("utf-8").strip()


def get_content_rights(content_id: str, tool_context: ToolContext) -> dict:
    """Returns where and until when one title may be streamed or broadcast.

    Use it for distribution-rights questions. If you only know the title name, look up
    its content_id in the content_catalogue table first.

    Args:
        content_id: Catalogue ID of the title, for example "C007".

    Returns:
        dict: {"status": "ok", "rights": {...}} with regions (ISO country codes), expiry
        date and editorial owner; {"status": "denied", "message": str} when the user's
        business unit may not read rights; or {"status": "error", "message": str}.
    """
    business_unit = str(tool_context.state.get("user:business_unit", "")).lower()
    if business_unit not in RIGHTS_READERS:
        return {
            "status": "denied",
            "message": f"Business unit '{business_unit or 'unknown'}' may not read distribution rights.",
        }
    if not settings.content_api_url:
        return {
            "status": "error",
            "message": "The content API is not connected yet (CONTENT_API_URL unset).",
        }
    try:
        response = requests.get(
            f"{settings.content_api_url.rstrip('/')}/titles/{content_id.strip().upper()}",
            headers={"x-apikey": apigee_key()},
            timeout=10,
        )
    except requests.RequestException as exc:
        return {"status": "error", "message": f"content API unreachable: {exc}"}
    if response.status_code == 200:
        rights = response.json()
        # Session-scoped note of what was checked; downstream agents can read it.
        checked = list(tool_context.state.get("rights_checked", []))
        tool_context.state["rights_checked"] = [
            *checked,
            rights.get("content_id", content_id),
        ]
        return {"status": "ok", "rights": rights}
    return {
        "status": "error",
        "message": f"content API returned HTTP {response.status_code}: {response.text[:200]}",
    }
