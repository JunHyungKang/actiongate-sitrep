#!/usr/bin/env python3
"""Evaluate judge-visible ActionGate artifacts across deterministic scenarios."""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from handler import _normalize, _source_text, handler  # noqa: E402
from sitrep_agent.sdk import AgentInput, Ctx  # noqa: E402


def fact(value: str, evidence: str) -> dict[str, str]:
    return {"value": value, "evidence": evidence}


COMPLETE_SUMMARY = (
    "Objective: Ship Acme rollout plan. Maya owns the rollout plan. "
    "Deadline: 2026-07-20 17:00 KST. Deliverable: Acme rollout plan. "
    "Definition of done: Acme approves the rollout plan. Dependency: legal approval."
)


SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "ambiguous-attendee-owner",
        "expected": "HOLD",
        "input": {
            "task": {
                "title": "Ship launch plan",
                "description": "Maya attended the meeting. Deadline: 2026-07-20 17:00 KST.",
            },
            "summary": (
                "Deliverable: launch plan. Definition of done: approved by Acme. "
                "Dependency: legal review."
            ),
            "attendees": [{"name": "Maya"}],
        },
        "draft": {
            "objective": fact("Ship launch plan", "Ship launch plan"),
            "owner": fact("Maya", "Maya attended the meeting"),
            "deadline": fact(
                "2026-07-20 17:00 KST", "Deadline: 2026-07-20 17:00 KST"
            ),
            "deliverables": [fact("launch plan", "Deliverable: launch plan")],
            "acceptance_criteria": [
                fact("approved by Acme", "Definition of done: approved by Acme")
            ],
            "dependencies": [fact("legal review", "Dependency: legal review")],
        },
        "questions": ("Who is the directly responsible owner?",),
        "forbidden": ("Maya",),
    },
    {
        "id": "speaker-attribution-trap",
        "expected": "HOLD",
        "input": {
            "task": {
                "title": "Ship launch plan",
                "description": "Maya said Jordan owns the launch plan.",
            },
            "summary": "",
            "attendees": [{"name": "Maya"}, {"name": "Jordan"}],
        },
        "draft": {
            "objective": fact("Ship launch plan", "Ship launch plan"),
            "owner": fact("Maya", "Maya said Jordan owns the launch plan"),
        },
        "questions": (
            "What is the calendar deadline or review date, including timezone?",
            "What exact artifact or outcome must be delivered?",
            "How will the team decide this action is done?",
            "What dependencies or approvals can block this action, or are there none?",
        ),
        "forbidden": ("Maya",),
    },
    {
        "id": "relative-deadline-trap",
        "expected": "HOLD",
        "input": {
            "task": {
                "title": "Ship launch plan",
                "description": "Owner: Maya. Deadline: next Friday.",
            },
            "summary": (
                "Deliverable: launch plan. Definition of done: approved by Acme. "
                "Dependency: legal review."
            ),
            "attendees": [{"name": "Maya"}],
        },
        "draft": {
            "objective": fact("Ship launch plan", "Ship launch plan"),
            "owner": fact("Maya", "Owner: Maya"),
            "deadline": fact("next Friday", "Deadline: next Friday"),
            "deliverables": [fact("launch plan", "Deliverable: launch plan")],
            "acceptance_criteria": [
                fact("approved by Acme", "Definition of done: approved by Acme")
            ],
            "dependencies": [fact("legal review", "Dependency: legal review")],
        },
        "questions": ("What is the calendar deadline or review date, including timezone?",),
    },
    {
        "id": "fully-supported-contract",
        "expected": "PROCEED",
        "input": {
            "task": {
                "title": "Ship Acme rollout plan",
                "description": (
                    "Maya will deliver the Acme rollout plan by "
                    "2026-07-20 17:00 KST."
                ),
            },
            "summary": COMPLETE_SUMMARY,
            "attendees": [{"name": "Maya"}],
        },
        "llm": "unexpected",
        "questions": (),
    },
    {
        "id": "cross-field-evidence-contamination",
        "expected": "HOLD",
        "input": {
            "task": {
                "title": "Ship launch plan",
                "description": (
                    "Maya owns the rollout plan. "
                    "Deadline: 2026-07-20 17:00 KST."
                ),
            },
            "summary": "",
            "attendees": [{"name": "Maya"}],
        },
        "draft": {
            "objective": fact("Ship launch plan", "Ship launch plan"),
            "owner": fact("Maya", "Maya owns the rollout plan"),
            "deadline": fact(
                "2026-07-20 17:00 KST", "Deadline: 2026-07-20 17:00 KST"
            ),
            "deliverables": [
                fact("Maya owns the rollout plan", "Maya owns the rollout plan")
            ],
            "acceptance_criteria": [
                fact("Maya owns the rollout plan", "Maya owns the rollout plan")
            ],
            "dependencies": [
                fact("Maya owns the rollout plan", "Maya owns the rollout plan")
            ],
        },
        "questions": (
            "What exact artifact or outcome must be delivered?",
            "How will the team decide this action is done?",
            "What dependencies or approvals can block this action, or are there none?",
        ),
    },
    {
        "id": "provider-independent-explicit-contract",
        "expected": "PROCEED",
        "input": {
            "task": {
                "title": "Ship Acme rollout plan",
                "description": (
                    "Maya will deliver the Acme rollout plan by "
                    "2026-07-20 17:00 KST."
                ),
            },
            "summary": COMPLETE_SUMMARY,
            "attendees": [{"name": "Maya"}],
        },
        "llm": "unexpected",
        "questions": (),
    },
)


class StaticLLM:
    model = "static"

    def __init__(self, draft: dict[str, Any]):
        self.draft = draft

    async def complete(self, **_kwargs: Any) -> str:
        return json.dumps(self.draft)


class UnexpectedLLM:
    model = "must-not-run"

    async def complete(self, **_kwargs: Any) -> str:
        raise AssertionError("explicit contracts must skip the provider")


@dataclass(frozen=True)
class ScenarioResult:
    case_id: str
    expected: str
    actual: str
    unsupported_confirmed: int
    forbidden_confirmed: int
    questions_found: int
    questions_expected: int
    artifacts_safe: bool


def _contract_rows(markdown: str) -> list[tuple[str, str, str]]:
    section = markdown.split("## Confirmed execution contract", 1)[1].split("\n## ", 1)[0]
    rows: list[tuple[str, str, str]] = []
    for line in section.splitlines():
        if not line.startswith("|") or "---" in line or "Confirmed value" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 3:
            rows.append((cells[0], cells[1], cells[2].strip('"')))
    return rows


async def evaluate() -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    for scenario in SCENARIOS:
        payload = scenario["input"]
        agent_input = AgentInput(agent={}, **payload)
        llm = (
            UnexpectedLLM()
            if scenario.get("llm") == "unexpected"
            else StaticLLM(scenario.get("draft", {}))
        )
        output = await handler(agent_input, Ctx(instructions="", tools=[], llm=llm))
        markdown = output["artifacts"][0]["content"]
        html = output["artifacts"][1]["content"]
        decision = re.search(r"Decision: (HOLD|PROCEED)", markdown)
        if not decision:
            raise ValueError(f"missing decision in {scenario['id']}")

        source = _normalize(_source_text(agent_input))
        rows = _contract_rows(markdown)
        confirmed = [row for row in rows if row[1] != "Not confirmed"]
        unsupported = sum(
            row[2] == "-" or _normalize(row[2]) not in source for row in confirmed
        )
        confirmed_values = {_normalize(row[1]) for row in confirmed}
        forbidden = sum(
            _normalize(value) in confirmed_values for value in scenario.get("forbidden", ())
        )
        expected_questions = scenario.get("questions", ())
        found_questions = sum(question in markdown for question in expected_questions)
        safe = (
            "## Confirmed execution contract" in markdown
            and "## Questions to close" in markdown
            and "What happens next" in html
            and "Verified execution contract" in html
            and "<script" not in html.casefold()
        )
        results.append(
            ScenarioResult(
                case_id=scenario["id"],
                expected=scenario["expected"],
                actual=decision.group(1),
                unsupported_confirmed=unsupported,
                forbidden_confirmed=forbidden,
                questions_found=found_questions,
                questions_expected=len(expected_questions),
                artifacts_safe=safe,
            )
        )
    return results


def summarize(results: list[ScenarioResult]) -> dict[str, int]:
    return {
        "correct": sum(result.actual == result.expected for result in results),
        "false_proceed": sum(
            result.actual == "PROCEED" and result.expected == "HOLD" for result in results
        ),
        "false_hold": sum(
            result.actual == "HOLD" and result.expected == "PROCEED" for result in results
        ),
        "unsupported_confirmed": sum(result.unsupported_confirmed for result in results),
        "forbidden_confirmed": sum(result.forbidden_confirmed for result in results),
        "questions_found": sum(result.questions_found for result in results),
        "questions_expected": sum(result.questions_expected for result in results),
        "safe_artifacts": sum(result.artifacts_safe for result in results),
    }


def render_markdown(results: list[ScenarioResult]) -> str:
    metrics = summarize(results)
    lines = [
        "# ActionGate Scenario-Level Evaluation",
        "",
        "This deterministic suite runs complete ActionGate requests through the handler and",
        "checks the judge-visible Markdown and HTML artifacts. It does not call a hosted LLM.",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Decision accuracy | {metrics['correct']}/{len(results)} |",
        f"| False PROCEED | {metrics['false_proceed']} |",
        f"| False HOLD | {metrics['false_hold']} |",
        f"| Unsupported confirmed facts | {metrics['unsupported_confirmed']} |",
        f"| Forbidden owner confirmations | {metrics['forbidden_confirmed']} |",
        f"| Missing-field question recall | {metrics['questions_found']}/{metrics['questions_expected']} |",
        f"| Safe, complete artifact pairs | {metrics['safe_artifacts']}/{len(results)} |",
        "",
        "| Scenario | Expected | Actual | Unsupported | Questions | Artifacts |",
        "|---|---|---|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            f"| `{result.case_id}` | {result.expected} | {result.actual} | "
            f"{result.unsupported_confirmed} | "
            f"{result.questions_found}/{result.questions_expected} | "
            f"{'PASS' if result.artifacts_safe else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## Scope",
            "",
            "This suite validates deterministic end-to-end artifact behavior with controlled",
            "candidate extractions. Hosted-model extraction quality and signed SitRep Studio",
            "runs remain separate evidence layers.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    report = render_markdown(asyncio.run(evaluate()))
    if args.write:
        args.write.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
