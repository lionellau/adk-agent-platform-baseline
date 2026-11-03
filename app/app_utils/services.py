# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Modified: switchable session backends (in-memory, SQLite, Postgres, Cloud SQL,
# Agent Platform Sessions) and memory backends (in-memory, Memory Bank), selected
# by SESSION_BACKEND / MEMORY_BACKEND, as taught in the ch2 sessions/memory lab.

"""Process-wide ADK session/artifact/memory services shared by every serving surface.

Registered under ``shared://`` so the ADK web routes, the chat routes, the A2A path
and the reasoning_engine adapter share one instance: a session created on any
surface is visible to the others.

Backends (environment variables):

SESSION_BACKEND
  in_memory       lost on restart; unit tests and quick local runs
  sqlite          file on disk (SQLITE_PATH, default ./sessions.db); single process
  postgres        DATABASE_URL, e.g. postgresql+asyncpg://adk:pw@localhost:5432/adk_sessions
  cloud_sql       INSTANCE_CONNECTION_NAME + DB_USER + DB_PASS (Cloud Run with /cloudsql socket)
  agent_platform  Agent Platform Sessions on the engine in AGENT_ENGINE (or the runtime's own)
  auto (default)  agent_platform on Agent Runtime, else SESSION_SERVICE_URI, else in_memory

MEMORY_BACKEND
  in_memory       keyword match over this process's sessions (dev only)
  agent_platform  Memory Bank on the engine in AGENT_ENGINE (or the runtime's own)
  none            no memory service; memory tools are left out of the agent
  auto (default)  agent_platform when an engine is known, else in_memory
"""

from __future__ import annotations

import functools
import logging
import os
from urllib.parse import quote

from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.adk.cli.service_registry import get_service_registry
from google.adk.cli.utils.service_factory import (
    create_memory_service_from_options,
    create_session_service_from_options,
)

logger = logging.getLogger(__name__)

SESSION_SERVICE_URI = "shared://session"
ARTIFACT_SERVICE_URI = "shared://artifact"
MEMORY_SERVICE_URI = "shared://memory"

_AGENT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def agent_runtime_location() -> str:
    """Region for the Agent Runtime engine; it doesn't support "global"."""
    if location := os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION"):
        return location
    if region := os.environ.get("REGION"):
        return region
    location = os.environ.get("GOOGLE_CLOUD_LOCATION")
    if location and location != "global":
        return location
    return "us-central1"


def agent_engine_resource_name() -> str:
    """Full engine name that holds Sessions and Memory Bank, or "" if none is known.

    On Agent Runtime the runtime injects GOOGLE_CLOUD_AGENT_ENGINE_ID. Elsewhere
    (local, Cloud Run) set AGENT_ENGINE to the engine created by
    scripts/setup_agent_runtime_backend.py (a full resource name or a bare ID).
    """
    value = os.environ.get("AGENT_ENGINE") or os.environ.get(
        "GOOGLE_CLOUD_AGENT_ENGINE_ID", ""
    )
    if not value or value.startswith("FILL_IN"):
        return ""
    if value.startswith("projects/"):
        return value
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    return f"projects/{project}/locations/{agent_runtime_location()}/reasoningEngines/{value}"


def session_service_uri() -> str:
    """Resolve SESSION_BACKEND to an ADK session service URI."""
    backend = os.environ.get("SESSION_BACKEND", "auto").strip().lower()
    if backend == "auto":
        # On Agent Runtime (injected ID) or with a backend engine (AGENT_ENGINE).
        if agent_engine_resource_name():
            backend = "agent_platform"
        elif os.environ.get("SESSION_SERVICE_URI"):
            return os.environ["SESSION_SERVICE_URI"]
        else:
            backend = "in_memory"
    if backend == "in_memory":
        return "memory://"
    if backend == "sqlite":
        return "sqlite:///" + os.environ.get("SQLITE_PATH", "sessions.db")
    if backend == "postgres":
        url = os.environ.get("DATABASE_URL", "")
        if not url.startswith("postgresql"):
            raise ValueError(
                "SESSION_BACKEND=postgres needs DATABASE_URL=postgresql+asyncpg://..."
            )
        return url
    if backend == "cloud_sql":
        user = quote(os.environ.get("DB_USER", "postgres"), safe="")
        password = quote(os.environ.get("DB_PASS", ""), safe="")
        name = os.environ.get("DB_NAME", "postgres")
        instance = os.environ.get("INSTANCE_CONNECTION_NAME", "")
        if not (instance and password):
            raise ValueError(
                "SESSION_BACKEND=cloud_sql needs INSTANCE_CONNECTION_NAME and DB_PASS"
            )
        # URL-encode the instance; '[' would otherwise trigger IPv6 parsing.
        return f"postgresql+asyncpg://{user}:{password}@/{name}?host=/cloudsql/{instance.replace(':', '%3A')}"
    if backend == "agent_platform":
        engine = agent_engine_resource_name()
        if not engine:
            raise ValueError(
                "SESSION_BACKEND=agent_platform needs AGENT_ENGINE (run scripts/setup_agent_runtime_backend.py)"
            )
        return f"agentengine://{engine}"
    raise ValueError(f"Unknown SESSION_BACKEND: {backend}")


def memory_service_uri() -> str | None:
    """Resolve MEMORY_BACKEND to an ADK memory service URI (None = no memory)."""
    backend = os.environ.get("MEMORY_BACKEND", "auto").strip().lower()
    if backend == "auto":
        backend = "agent_platform" if agent_engine_resource_name() else "in_memory"
    if backend == "none":
        return None
    if backend == "in_memory":
        return "memory://"
    if backend == "agent_platform":
        engine = agent_engine_resource_name()
        if not engine:
            raise ValueError("MEMORY_BACKEND=agent_platform needs AGENT_ENGINE")
        return f"agentengine://{engine}"
    raise ValueError(f"Unknown MEMORY_BACKEND: {backend}")


@functools.cache
def get_session_service():
    """Process-wide session service shared across every serving surface."""
    uri = session_service_uri()
    logger.info("session backend: %s", uri.split("://")[0] if "@" in uri else uri)
    return create_session_service_from_options(
        base_dir=_AGENT_DIR, session_service_uri=uri
    )


@functools.cache
def get_memory_service():
    """Process-wide memory service, or None when MEMORY_BACKEND=none."""
    uri = memory_service_uri()
    logger.info("memory backend: %s", uri)
    if uri is None:
        return None
    return create_memory_service_from_options(
        base_dir=_AGENT_DIR, memory_service_uri=uri
    )


@functools.cache
def get_artifact_service():
    """Process-wide artifact service: GCS when a bucket is set, else in-memory."""
    if bucket := os.environ.get("LOGS_BUCKET_NAME"):
        return GcsArtifactService(bucket_name=bucket)
    return InMemoryArtifactService()


_registry = get_service_registry()
_registry.register_session_service("shared", lambda uri, **kw: get_session_service())
_registry.register_artifact_service("shared", lambda uri, **kw: get_artifact_service())
_registry.register_memory_service("shared", lambda uri, **kw: get_memory_service())
