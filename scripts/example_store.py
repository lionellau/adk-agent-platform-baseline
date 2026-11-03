"""Example Store: dynamic few-shot examples, retrieved per query (the ch2 lab's examples service).

The agent uses them through ADK's ExampleTool when EXAMPLE_STORE_NAME is set: for each
request the most similar stored examples are added to the prompt, so answers follow the
house format without a longer system prompt.

Usage (repo root; GOOGLE_CLOUD_PROJECT and REGION set):
  uv run python scripts/example_store.py create            # prints EXAMPLE_STORE_NAME=...
  uv run python scripts/example_store.py upload            # upserts scripts/examples/*.json
  uv run python scripts/example_store.py list
  uv run python scripts/example_store.py search "Top drama titles last month?"
  uv run python scripts/example_store.py remove            # removes all examples (store kept)
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

from dotenv import load_dotenv

load_dotenv()  # the repo's .env; variables already set in the shell win

EXAMPLES_DIR = pathlib.Path(__file__).parent / "examples"
EMBEDDING_MODEL = os.environ.get("EXAMPLE_STORE_EMBEDDING_MODEL", "text-embedding-005")


def _client():
    import agentplatform

    return agentplatform.Client(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("REGION", "us-central1"),
    )


def _store() -> str:
    name = os.environ.get("EXAMPLE_STORE_NAME", "")
    if not name:
        sys.exit("FIX: set EXAMPLE_STORE_NAME (run: example_store.py create)")
    return name


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "create":
        import vertexai
        from vertexai.preview import example_stores

        vertexai.init(
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.environ.get("REGION", "us-central1"),
        )
        store = example_stores.ExampleStore.create(
            example_store_config=example_stores.ExampleStoreConfig(
                vertex_embedding_model=EMBEDDING_MODEL
            ),
            display_name="mc-platform-examples",
        )
        print(f"EXAMPLE_STORE_NAME={store.resource_name}")
    elif action == "upload":
        files = sorted(EXAMPLES_DIR.glob("*.json"))
        examples = [json.loads(f.read_text()) for f in files]
        for i in range(0, len(examples), 5):  # at most 5 examples per request
            _client().example_stores.upsert_examples(
                name=_store(),
                examples=[{"stored_contents_example": e} for e in examples[i : i + 5]],
            )
        print(f"uploaded {len(examples)} examples from {EXAMPLES_DIR}")
    elif action == "list":
        for ex in _client().example_stores.fetch_examples(name=_store()).examples or []:
            print(f"- {ex.example_id} | {ex.stored_contents_example.search_key}")
    elif action == "search":
        query = " ".join(sys.argv[2:]) or "Top titles last month?"
        res = _client().example_stores.search_examples(
            name=_store(),
            stored_contents_example_parameters={
                "content_search_key": {
                    "contents": [{"role": "user", "parts": [{"text": query}]}],
                    "search_key_generation_method": {"last_entry": {}},
                }
            },
            config={"top_k": 2},
        )
        for r in res.results or []:
            print(
                f"- similarity={r.similarity_score:.3f} | {r.example.stored_contents_example.search_key}"
            )
    elif action == "remove":
        client = _client()
        ids = [
            ex.example_id
            for ex in client.example_stores.fetch_examples(name=_store()).examples or []
        ]
        if ids:
            client.example_stores.remove_examples(
                name=_store(), config={"example_ids": ids}
            )
        print(f"removed {len(ids)} examples")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
