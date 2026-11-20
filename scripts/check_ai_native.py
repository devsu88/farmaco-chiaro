#!/usr/bin/env python3
"""Deterministic check of the AI-native SDLC artifacts.

This is the configuration eval: it does not call a model and needs no
credentials, so it can run on every pull request. It checks that the process
artifacts exist, that skills and agents have usable frontmatter, that no secret
or generated build artifact is tracked, and that the runtime snapshot is
present.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "AGENTS.md",
    "CLAUDE.md",
    "REVIEW.md",
    "README.md",
    "opencode.jsonc",
    "scripts/check_ai_native.py",
    "scripts/smoke.py",
    "scripts/log_report.py",
    ".github/workflows/smoke.yml",
    ".github/workflows/ai-native.yml",
    ".github/pull_request_template.md",
    "backend/tests/test_safety_contract.py",
    "backend/data/rag/chunks.jsonl",
    "backend/data/rag/sections.jsonl",
    "backend/data/rag/documento.jsonl",
    "backend/data/rag/farmaci.json",
    "docs/ai-native/README.md",
]

FORBIDDEN_DIRS = {
    "node_modules",
    ".next",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".playwright-mcp",
    ".superpowers",
}

SKILL_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    _, _, rest = text.partition("---")
    block, _, _ = rest.partition("---")
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("\"'")
    return fields


def _strip_jsonc(text: str) -> str:
    """Remove // comments outside strings so json.loads can parse the file."""
    out: list[str] = []
    in_string = False
    escaped = False
    i = 0
    while i < len(text):
        char = text[i]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            i += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            i += 1
            continue
        if char == "/" and i + 1 < len(text) and text[i + 1] == "/":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _tracked_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _forbidden_tracked(path: str) -> bool:
    parts = path.split("/")
    name = parts[-1]
    if name == ".env":
        return True
    if name.startswith(".env.") and name != ".env.example":
        return True
    if any(part in FORBIDDEN_DIRS for part in parts):
        return True
    if path.startswith("backend/data/cache/"):
        return True
    if path in {"frontend/tsconfig.tsbuildinfo"}:
        return True
    return False


def main() -> int:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    for relative in REQUIRED:
        path = ROOT / relative
        require(path.is_file(), f"missing required file: {relative}")
        if path.is_file():
            require(path.stat().st_size > 0, f"empty required file: {relative}")

    agents_md = (ROOT / "AGENTS.md").read_text(encoding="utf-8") if (ROOT / "AGENTS.md").is_file() else ""
    for token in ("make test", "make lint", "make build", "make check", "REVIEW.md", "docs/ai-native"):
        require(token in agents_md, f"AGENTS.md does not mention {token!r}")

    claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8") if (ROOT / "CLAUDE.md").is_file() else ""
    require("AGENTS.md" in claude_md, "CLAUDE.md is not a pointer to AGENTS.md")

    review_md = (ROOT / "REVIEW.md").read_text(encoding="utf-8") if (ROOT / "REVIEW.md").is_file() else ""
    for token in ("## Passes", "Important"):
        require(token in review_md, f"REVIEW.md is missing {token!r}")
    require("nits" in review_md.lower(), "REVIEW.md does not define nits")

    readme_md = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").is_file() else ""
    require("make check" in readme_md, "README.md does not document `make check`")

    config_path = ROOT / "opencode.jsonc"
    if config_path.is_file():
        try:
            config = json.loads(_strip_jsonc(config_path.read_text(encoding="utf-8")))
            require(isinstance(config.get("permissions"), list), "opencode.jsonc has no permissions array")
        except json.JSONDecodeError as exc:
            errors.append(f"opencode.jsonc is not valid JSONC: {exc}")

    skills = sorted((ROOT / ".opencode/skills").glob("*/SKILL.md"))
    require(bool(skills), "no skills found under .opencode/skills/")
    for skill in skills:
        fields = _frontmatter(skill)
        require(bool(fields.get("name")), f"{skill}: missing frontmatter name")
        require(bool(fields.get("description")), f"{skill}: missing frontmatter description")
        require(
            bool(SKILL_ID.match(skill.parent.name)),
            f"{skill.parent.name}: skill id is not kebab-case",
        )

    agents = sorted((ROOT / ".opencode/agents").glob("*.md"))
    require(bool(agents), "no agents found under .opencode/agents/")
    for agent in agents:
        fields = _frontmatter(agent)
        require(bool(fields.get("description")), f"{agent}: missing frontmatter description")

    initiatives = [
        path
        for path in sorted((ROOT / "docs/ai-native").glob("*"))
        if path.is_dir() and not path.name.startswith(".")
    ]
    complete = [
        path
        for path in initiatives
        if all((path / name).is_file() and (path / name).stat().st_size > 0 for name in ("intent.md", "spec.md", "plan.md"))
    ]
    require(bool(complete), "no docs/ai-native/<date>-<slug>/ with intent, spec and plan")

    tracked = _tracked_files()
    forbidden = [path for path in tracked if _forbidden_tracked(path)]
    require(not forbidden, f"forbidden tracked files: {', '.join(forbidden[:10])}")

    farmaci_path = ROOT / "backend/data/rag/farmaci.json"
    farmaci = 0
    if farmaci_path.is_file():
        try:
            farmaci = len(json.loads(farmaci_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            errors.append(f"farmaci.json is not valid JSON: {exc}")
    require(farmaci > 0, "backend/data/rag/farmaci.json has no drugs")

    for name in ("chunks.jsonl", "sections.jsonl", "documento.jsonl"):
        path = ROOT / "backend/data/rag" / name
        if path.is_file():
            require(path.stat().st_size > 0, f"{name} is empty")

    if errors:
        print("AI-native process check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("AI-native process check")
    print(f"  ok  required artifacts ({len(REQUIRED)})")
    print(f"  ok  skills ({len(skills)})")
    print(f"  ok  agents ({len(agents)})")
    print(f"  ok  initiatives ({len(complete)})")
    print(f"  ok  tracked files clean ({len(tracked)})")
    print(f"  ok  runtime snapshot ({farmaci} drugs)")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
