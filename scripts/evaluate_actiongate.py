#!/usr/bin/env python3
"""Compare naive extraction with ActionGate's deterministic evidence audit."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from handler import FIELD_SPECS, _audit_plan, _gate  # noqa: E402

DEFAULT_CASES = ROOT / "evals" / "actiongate_cases.json"


@dataclass(frozen=True)
class Result:
    case_id: str
    expected: str
    naive: str
    actiongate: str
    naive_risk_error: int
    actiongate_risk_error: int


def _naive_decision(plan: dict[str, Any]) -> str:
    return "PROCEED" if all(plan.get(key) for key, _label, _weight in FIELD_SPECS) else "HOLD"


def evaluate(cases: list[dict[str, Any]]) -> list[Result]:
    results: list[Result] = []
    for case in cases:
        plan = case["plan"]
        audited = _audit_plan(plan, case["source"])
        expected_risks = int(case.get("expected_confirmed_risks", 0))
        naive_risks = sum(
            1 for risk in plan.get("risks", []) if risk.get("kind") == "stated"
        )
        actiongate_risks = sum(
            1 for risk in audited.get("risks", []) if risk.get("kind") == "stated"
        )
        results.append(
            Result(
                case_id=case["id"],
                expected=case["expected_decision"],
                naive=_naive_decision(plan),
                actiongate=_gate(audited)[1],
                naive_risk_error=abs(naive_risks - expected_risks),
                actiongate_risk_error=abs(actiongate_risks - expected_risks),
            )
        )
    return results


def summarize(results: list[Result]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for system in ("naive", "actiongate"):
        predictions = [getattr(result, system) for result in results]
        summary[system] = {
            "correct": sum(prediction == result.expected for prediction, result in zip(predictions, results)),
            "false_proceed": sum(
                prediction == "PROCEED" and result.expected == "HOLD"
                for prediction, result in zip(predictions, results)
            ),
            "false_hold": sum(
                prediction == "HOLD" and result.expected == "PROCEED"
                for prediction, result in zip(predictions, results)
            ),
            "risk_errors": sum(getattr(result, f"{system}_risk_error") for result in results),
        }
    return summary


def render_markdown(results: list[Result]) -> str:
    summary = summarize(results)
    lines = [
        "# ActionGate Adversarial Evaluation",
        "",
        "This deterministic suite isolates the policy layer: both systems receive the same",
        "candidate extraction, while ActionGate additionally audits ownership, deadline, and",
        "risk evidence before allowing execution.",
        "",
        "| System | Correct | False PROCEED | False HOLD | Risk confirmation errors |",
        "|---|---:|---:|---:|---:|",
    ]
    for system, label in (("naive", "Presence-only baseline"), ("actiongate", "ActionGate")):
        metrics = summary[system]
        lines.append(
            f"| {label} | {metrics['correct']}/{len(results)} | {metrics['false_proceed']} | "
            f"{metrics['false_hold']} | {metrics['risk_errors']} |"
        )
    lines.extend(
        [
            "",
            "| Case | Expected | Presence-only | ActionGate |",
            "|---|---|---|---|",
            *(
                f"| `{result.case_id}` | {result.expected} | {result.naive} | {result.actiongate} |"
                for result in results
            ),
            "",
            "## Scope",
            "",
            "These are policy-layer regression cases, not a claim about a particular hosted LLM's",
            "extraction accuracy. Live SitRep HOLD and PROCEED runs are tracked separately in",
            "`docs/submission-status.md`.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    output = render_markdown(evaluate(cases))
    if args.write:
        args.write.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
