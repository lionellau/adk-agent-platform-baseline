"""Publish a skill folder to the Agent Platform Skills Registry (the ADK skills lab, task 4).

Usage (repo root; GOOGLE_CLOUD_PROJECT and REGION set):
  uv run python scripts/publish_skill.py app/skills/content-performance-report
  uv run python scripts/publish_skill.py --list

The folder name must equal the SKILL.md `name`. The registry keeps versions (revisions),
so other teams' agents can download the same reviewed skill.
"""

from __future__ import annotations

import os
import pathlib
import re
import sys

from dotenv import load_dotenv

load_dotenv()  # the repo's .env; variables already set in the shell win


def _client():
    import agentplatform

    return agentplatform.Client(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("REGION", "us-central1"),
    )


def _frontmatter(skill_md: pathlib.Path) -> dict:
    text = skill_md.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        sys.exit(f"FIX: {skill_md} has no YAML frontmatter")
    out = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    if sys.argv[1] == "--list":
        for s in _client().skills.list():
            print(f"- {s.name} | {getattr(s, 'display_name', '')}")
        return 0
    folder = pathlib.Path(sys.argv[1])
    meta = _frontmatter(folder / "SKILL.md")
    name = meta.get("name", "")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or len(name) > 64:
        sys.exit(f"FIX: skill name '{name}' must be kebab-case, at most 64 characters")
    if folder.name != name:
        sys.exit(f"FIX: folder '{folder.name}' must equal the skill name '{name}'")
    skill = _client().skills.create(
        skill_id=name,
        display_name=name.replace("-", " ").capitalize(),
        description=meta.get("description", "")[:1024],
        config={"local_path": str(folder), "wait_for_completion": True},
    )
    print(f"published: {getattr(skill, 'name', skill)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
