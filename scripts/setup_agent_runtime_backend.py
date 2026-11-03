"""Create (or update) the Agent Runtime engine that hosts Agent Platform Sessions and Memory Bank.

Use it when the agent runs somewhere other than Agent Runtime (local dev, Cloud Run):
the engine then only stores sessions and memories (the ch2 lab's setup_agentruntime.py).
When the agent itself is deployed to Agent Runtime with `agents-cli deploy`, apply the
same Memory Bank settings to that engine with --engine.

Usage (repo root, after `source ~/platform.env`):
  uv run python scripts/setup_agent_runtime_backend.py --check            # validate config only, no API call
  uv run python scripts/setup_agent_runtime_backend.py                    # find or create "mc-platform-backend"
  uv run python scripts/setup_agent_runtime_backend.py --engine projects/.../reasoningEngines/ID   # update an engine

Memory Bank settings (Course 6 ch. 3):
- managed topics: preferences, explicit instructions, key conversation details;
  USER_PERSONAL_INFO is deliberately left out (privacy by default);
- one custom topic, content_interests, with a few-shot extraction example (always pair
  custom topics with examples);
- a structured user profile (memory_type STRUCTURED_PROFILE), read with retrieve_profiles;
- revisions kept, memories expire after MEMORY_TTL_DAYS (default 30).
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # the repo's .env; variables already set in the shell win

DISPLAY_NAME = os.environ.get("AGENT_ENGINE_DISPLAY_NAME", "mc-platform-backend")
TTL_DAYS = int(os.environ.get("MEMORY_TTL_DAYS", "30"))
LABELS = {
    "env": os.environ.get("ENV_NAME", "sandbox"),
    "app": "agent-platform",
    "bu": "platform",
}


def memory_bank_config() -> dict:
    return {
        "customization_configs": [
            {
                "memory_topics": [
                    {
                        "managed_memory_topic": {
                            "managed_topic_enum": "USER_PREFERENCES"
                        }
                    },
                    {
                        "managed_memory_topic": {
                            "managed_topic_enum": "EXPLICIT_INSTRUCTIONS"
                        }
                    },
                    {
                        "managed_memory_topic": {
                            "managed_topic_enum": "KEY_CONVERSATION_DETAILS"
                        }
                    },
                    {
                        "custom_memory_topic": {
                            "label": "content_interests",
                            "description": "Titles, genres, platforms or business units the user repeatedly asks about or says they follow.",
                        }
                    },
                ],
                "generate_memories_examples": [
                    {
                        "conversation_source": {
                            "events": [
                                {
                                    "content": {
                                        "role": "user",
                                        "parts": [
                                            {
                                                "text": "I look after the drama slate, mostly Lion City Hearts and Merlion Mysteries."
                                            }
                                        ],
                                    }
                                },
                                {
                                    "content": {
                                        "role": "model",
                                        "parts": [
                                            {
                                                "text": "Noted. Do you want weekly figures for both?"
                                            }
                                        ],
                                    }
                                },
                            ]
                        },
                        "generated_memories": [
                            {
                                "fact": "Follows the drama titles Lion City Hearts and Merlion Mysteries.",
                                "topics": [
                                    {"custom_memory_topic_label": "content_interests"}
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "structured_memory_configs": [
            {
                "schema_configs": [
                    {
                        "id": "user-profile",
                        "memory_type": "STRUCTURED_PROFILE",
                        "memory_schema": {
                            "type": "OBJECT",
                            "properties": {
                                "preferred_format": {
                                    "type": "STRING",
                                    "description": "How the user wants answers, e.g. 'at most 3 bullets'.",
                                },
                                "business_focus": {
                                    "type": "STRING",
                                    "description": "Business unit or area the user works on.",
                                },
                                "followed_titles": {
                                    "type": "ARRAY",
                                    "items": {"type": "STRING"},
                                    "description": "Titles the user follows.",
                                },
                            },
                        },
                    }
                ]
            }
        ],
        "ttl_config": {"default_ttl": f"{TTL_DAYS * 24 * 3600}s"},
        "disable_memory_revisions": False,
    }


def validate() -> None:
    """Fail fast, offline, if the SDK rejects the config shape."""
    import warnings

    from agentplatform import types

    with warnings.catch_warnings():
        # The SDK only warns on an unknown enum value (for example a misspelled topic); make it fatal.
        warnings.filterwarnings("error", message=".*is not a valid.*")
        types.ReasoningEngineContextSpec.model_validate(
            {"memory_bank_config": memory_bank_config()}
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--engine", help="Existing engine to update instead of find-or-create."
    )
    parser.add_argument(
        "--check", action="store_true", help="Validate the config only (no API call)."
    )
    args = parser.parse_args()

    validate()
    print("memory bank config: valid")
    if args.check:
        return 0

    import agentplatform

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.environ.get("REGION", "us-central1")
    client = agentplatform.Client(project=project, location=region)
    context_spec = {"memory_bank_config": memory_bank_config()}

    if args.engine:
        runtime = client.runtimes.update(
            name=args.engine, config={"context_spec": context_spec}
        )
        print(f"updated Memory Bank settings on {args.engine}")
        name = args.engine
    else:
        existing = list(
            client.runtimes.list(config={"filter": f'display_name="{DISPLAY_NAME}"'})
        )
        if existing:
            runtime = existing[0]
            print(
                f"found existing engine '{DISPLAY_NAME}' (settings unchanged; use --engine to update)"
            )
        else:
            runtime = client.runtimes.create(
                config={
                    "display_name": DISPLAY_NAME,
                    "context_spec": context_spec,
                    "labels": LABELS,
                }
            )
            print(f"created engine '{DISPLAY_NAME}'")
        name = runtime.api_resource.name
    print(f"AGENT_ENGINE={name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
