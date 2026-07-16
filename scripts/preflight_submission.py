#!/usr/bin/env python3
"""Run deterministic local checks for the SitRep/Kaggle submission package."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


REQUIRED_FILES = (
    "LICENSE",
    "README.md",
    "agent.json",
    "app.py",
    "handler.py",
    "prompt.txt",
    "render.yaml",
    "docs/submission-draft.md",
    "docs/submission-status.md",
)

SECRET_PATTERNS = (
    re.compile(r"KGAT_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
)


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))


def tracked_files(root: Path) -> list[Path] | None:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=False)
    if result.returncode != 0:
        return None
    return [root / path.decode() for path in result.stdout.split(b"\0") if path]


def run_checks(root: Path) -> list[Check]:
    checks: list[Check] = []
    missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
    detail = "missing: " + ", ".join(missing) if missing else "present"
    checks.append(Check("required files", not missing, detail))

    try:
        metadata = json.loads((root / "agent.json").read_text())
        required = {"name", "tagline", "description", "category", "taskTypes", "pricing"}
        absent = sorted(required - metadata.keys())
        detail = "missing keys: " + ", ".join(absent) if absent else "required keys present"
        checks.append(Check("agent metadata", not absent, detail))
    except (OSError, json.JSONDecodeError) as exc:
        checks.append(Check("agent metadata", False, str(exc)))

    license_path = root / "LICENSE"
    license_text = license_path.read_text(errors="replace") if license_path.exists() else ""
    has_mit = "MIT License" in license_text
    checks.append(Check("MIT license", has_mit, "MIT marker found" if has_mit else "missing"))

    draft = root / "docs/submission-draft.md"
    count = word_count(draft.read_text(errors="replace")) if draft.exists() else 0
    checks.append(Check("writeup length", 0 < count <= 1000, f"{count} words (limit: 1000)"))

    render_path = root / "render.yaml"
    render_text = render_path.read_text(errors="replace") if render_path.exists() else ""
    has_keys = all(key in render_text for key in ("SITREP_AGENT_SECRET", "LLM_API_KEY"))
    has_slots = render_text.count("sync: false") >= 2
    detail = "dashboard-managed" if has_keys and has_slots else "missing sync:false slots"
    checks.append(Check("deployment secrets", has_keys and has_slots, detail))

    tracked = tracked_files(root)
    if tracked is None:
        checks.append(Check("tracked secret scan", False, "git ls-files failed"))
    else:
        findings: list[str] = []
        for path in tracked:
            if path.name == ".env":
                findings.append(str(path.relative_to(root)))
                continue
            try:
                if path.stat().st_size > 1_000_000:
                    continue
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                findings.append(str(path.relative_to(root)))
        detail = "possible secrets: " + ", ".join(findings) if findings else "clear"
        checks.append(Check("tracked secret scan", not findings, detail))

    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    checks = run_checks(args.root.resolve())
    for check in checks:
        print(f"[{'PASS' if check.ok else 'FAIL'}] {check.name}: {check.detail}")
    return 0 if all(check.ok for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
