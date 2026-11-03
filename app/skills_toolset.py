"""Skills for the report writer (the ADK skills lab): inline, file-based and a meta-skill.

Progressive disclosure: the model first sees only each skill's name and description
(L1), loads the instructions when it decides to (L2), and reads reference files on
demand with load_skill_resource (L3). This keeps the base prompt small.
"""

from __future__ import annotations

import pathlib
import sys

from google.adk.skills import load_skill_from_dir, models
from google.adk.tools.skill_toolset import SkillToolset

SKILLS_PATH = pathlib.Path(__file__).parent / "skills"

# Inline skill: small, stable rules that fit in code.
number_formatting_skill = models.Skill(
    frontmatter=models.Frontmatter(
        name="number-formatting",
        description="Rules for writing audience numbers, percentages and date ranges consistently.",
    ),
    instructions=(
        "When you present audience figures:\n"
        "1. Use thousands separators (203,000), never abbreviations like 203k.\n"
        "2. Percentages: one decimal and a sign for changes (+5.3 %, -2.0 %).\n"
        "3. Always name the date range the numbers cover.\n"
        "4. When comparing two numbers, also give the difference."
    ),
)

# Meta-skill: generates new SKILL.md files that follow the Agent Skills specification.
skill_creator = models.Skill(
    frontmatter=models.Frontmatter(
        name="skill-creator",
        description="Creates new ADK-compatible skill definitions (SKILL.md) from requirements.",
    ),
    instructions=(
        "When asked to create a new skill, output one complete SKILL.md file.\n"
        "Read `references/skill-spec.md` first.\n"
        "Rules: kebab-case name of at most 64 characters; description under 1024 characters;\n"
        "clear numbered steps; long details go in references/; SKILL.md under 500 lines."
    ),
    resources=models.Resources(
        references={
            "skill-spec.md": (
                "# Agent Skills specification (summary)\n\n"
                "A skill is a folder whose name equals the `name` field. It contains SKILL.md and\n"
                "optional references/, assets/ and scripts/ folders.\n\n"
                "SKILL.md = YAML frontmatter (name, description) + Markdown instructions.\n"
                "The description is what the model reads to decide when to load the skill, so\n"
                "say what it does and when to use it. Name pattern: ^[a-z0-9]+(-[a-z0-9]+)*$.\n"
                "Point to detailed documents with `load_skill_resource` instead of inlining them."
            )
        }
    ),
)


def _load(name: str):
    path = SKILLS_PATH / name
    if not path.exists():
        print(f"Warning: skill directory '{name}' not found at {path}", file=sys.stderr)
    return load_skill_from_dir(path)


def report_skills() -> SkillToolset:
    """Skills used by the report writer."""
    return SkillToolset(
        skills=[
            number_formatting_skill,
            _load("content-performance-report"),
            skill_creator,
        ]
    )
