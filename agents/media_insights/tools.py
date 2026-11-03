"""Function tools. The Apigee API key is read from Secret Manager, never from code or .env."""
import functools
import os

import requests
from google.api_core.client_options import ClientOptions
from google.cloud import secretmanager


@functools.lru_cache(maxsize=1)
def apigee_key() -> str:
    """Returns this agent's Apigee API key (one key per business unit app)."""
    secret = os.environ.get("APIGEE_KEY_SECRET", "")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not secret or not project:
        return ""
    client = secretmanager.SecretManagerServiceClient(
        client_options=ClientOptions(quota_project_id=project))
    name = f"projects/{project}/secrets/{secret}/versions/latest"
    return client.access_secret_version(name=name).payload.data.decode("utf-8").strip()


def get_content_rights(content_id: str) -> dict:
    """Returns distribution rights for one title from the content rights API (served through Apigee).

    Use it when the user asks where or until when a title may be streamed or broadcast.
    If you only know the title name, first look up its content_id in the content_catalogue table.

    Args:
        content_id: The catalogue ID of the title, for example "C007".

    Returns:
        dict: {"status": "ok", "rights": {...}} with regions (ISO country codes), expiry date and
        editorial owner; or {"status": "error", "message": str} if the title is unknown or the call fails.
    """
    base = os.environ.get("CONTENT_API_URL", "")
    if not base:
        return {"status": "error", "message": "The content API is not connected yet (CONTENT_API_URL unset)."}
    try:
        r = requests.get(f"{base.rstrip('/')}/titles/{content_id.strip().upper()}",
                         headers={"x-apikey": apigee_key()}, timeout=10)
    except requests.RequestException as exc:
        return {"status": "error", "message": f"content API unreachable: {exc}"}
    if r.status_code == 200:
        return {"status": "ok", "rights": r.json()}
    return {"status": "error", "message": f"content API returned HTTP {r.status_code}: {r.text[:200]}"}
