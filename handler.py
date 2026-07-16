"""ActionGate: turn a meeting action into an evidence-backed execution contract."""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any

from sitrep_agent.sdk import AgentInput, Ctx

SYSTEM_PROMPT = Path(__file__).with_name("prompt.txt").read_text(encoding="utf-8").strip()

SCHEMA = """
{
  "objective": {"value": "...", "evidence": "exact quote"} | null,
  "owner": {"value": "...", "evidence": "exact quote"} | null,
  "deadline": {"value": "...", "evidence": "exact quote"} | null,
  "deliverables": [{"value": "...", "evidence": "exact quote"}],
  "acceptance_criteria": [{"value": "...", "evidence": "exact quote"}],
  "dependencies": [{"value": "...", "evidence": "exact quote"}],
  "risks": [{"value": "...", "evidence": "exact quote or empty", "kind": "stated|inferred"}],
  "next_steps": [{"action": "...", "owner": "...", "timing": "..."}],
  "questions": ["..."]
}
""".strip()


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    elif not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("LLM response did not contain a JSON object")
        text = text[start : end + 1]
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("LLM response must be a JSON object")
    return value


def _supported_fact(value: Any, source: str) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    fact = str(value.get("value") or "").strip()
    evidence = str(value.get("evidence") or "").strip()
    if (
        not fact
        or not evidence
        or _normalize(evidence) not in _normalize(source)
        or _normalize(fact) not in _normalize(evidence)
    ):
        return None
    return {"value": fact, "evidence": evidence}


def _supported_list(value: Any, source: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [fact for item in value if (fact := _supported_fact(item, source))]


def _specific_deadline(fact: dict[str, str] | None) -> dict[str, str] | None:
    if not fact:
        return None
    value = _normalize(fact["value"])
    relative_terms = (
        "today",
        "tomorrow",
        "next week",
        "this week",
        "soon",
        "later",
        "asap",
        "eod",
        "end of day",
    )
    relative_patterns = (r"\bin\s+\d+", r"\bnext\s+\d+", r"\bq[1-4]\b")
    absolute_patterns = (
        r"\b20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\b",
        r"\b\d{1,2}[-/.]\d{1,2}[-/.]20\d{2}\b",
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\s+\d{1,2},?\s+20\d{2}\b",
        r"\b\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)\s+20\d{2}\b",
    )
    if (
        any(term in value for term in relative_terms)
        or any(re.search(pattern, value) for pattern in relative_patterns)
        or not any(re.search(pattern, value) for pattern in absolute_patterns)
    ):
        return None
    return fact


def _clean_text_list(value: Any, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _audit_plan(plan: dict[str, Any], source: str) -> dict[str, Any]:
    # Being listed as an attendee is not evidence that a person owns the action.
    action_source = "\n".join(
        line for line in source.splitlines() if not line.startswith("Meeting attendees:")
    )
    audited: dict[str, Any] = {
        "objective": _supported_fact(plan.get("objective"), source),
        "owner": _supported_fact(plan.get("owner"), action_source),
        "deadline": _specific_deadline(_supported_fact(plan.get("deadline"), action_source)),
        "deliverables": _supported_list(plan.get("deliverables"), source),
        "acceptance_criteria": _supported_list(plan.get("acceptance_criteria"), source),
        "dependencies": _supported_list(plan.get("dependencies"), source),
        "questions": _clean_text_list(plan.get("questions")),
    }

    risks: list[dict[str, str]] = []
    for item in plan.get("risks") or []:
        if not isinstance(item, dict) or not str(item.get("value") or "").strip():
            continue
        kind = "stated" if item.get("kind") == "stated" else "inferred"
        evidence = str(item.get("evidence") or "").strip()
        if kind == "stated" and _normalize(evidence) not in _normalize(source):
            kind, evidence = "inferred", ""
        risks.append({"value": str(item["value"]).strip(), "kind": kind, "evidence": evidence})
    audited["risks"] = risks[:6]

    confirmed_owner = audited["owner"]["value"] if audited["owner"] else None
    confirmed_deadline = audited["deadline"]["value"] if audited["deadline"] else None
    steps: list[dict[str, str]] = []
    for item in plan.get("next_steps") or []:
        if not isinstance(item, dict) or not str(item.get("action") or "").strip():
            continue
        proposed_owner = str(item.get("owner") or "").strip()
        proposed_timing = str(item.get("timing") or "").strip()
        steps.append(
            {
                "action": str(item["action"]).strip(),
                "owner": (
                    confirmed_owner
                    if confirmed_owner and _normalize(proposed_owner) == _normalize(confirmed_owner)
                    else "TBD"
                ),
                "timing": (
                    confirmed_deadline
                    if confirmed_deadline
                    and _normalize(confirmed_deadline) in _normalize(proposed_timing)
                    else "TBD"
                ),
            }
        )
    audited["next_steps"] = steps[:6]
    return audited


def _missing_fields(plan: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    checks = (
        ("objective", "A specific objective"),
        ("owner", "A directly responsible owner"),
        ("deadline", "A deadline or review date"),
        ("deliverables", "Concrete deliverables"),
        ("acceptance_criteria", "A measurable definition of done"),
        ("dependencies", "Confirmed dependencies or an explicit 'none'"),
    )
    for key, label in checks:
        if not plan.get(key):
            missing.append(label)
    return missing


def _readiness_score(plan: dict[str, Any]) -> int:
    weights = {
        "objective": 20,
        "owner": 20,
        "deadline": 15,
        "deliverables": 15,
        "acceptance_criteria": 20,
        "dependencies": 10,
    }
    return sum(weight for key, weight in weights.items() if plan.get(key))


def _cell(value: str) -> str:
    return escape(value, quote=True).replace("|", "\\|").replace("\n", " ").strip()


def _render(title: str, plan: dict[str, Any]) -> str:
    score = _readiness_score(plan)
    missing = _missing_fields(plan)
    if not missing:
        status = "GREEN - READY"
    elif score >= 50:
        status = "YELLOW - NEEDS CLARIFICATION"
    else:
        status = "RED - BLOCKED"

    lines = [
        f"# ActionGate: {title}",
        "",
        f"**Execution readiness: {score}/100 - {status}**",
        "",
        "> Only claims backed by an exact quote from the task or meeting summary are treated as confirmed.",
        "",
        "## Confirmed execution contract",
        "",
        "| Field | Confirmed value | Evidence |",
        "|---|---|---|",
    ]
    for key, label in (("objective", "Objective"), ("owner", "Owner"), ("deadline", "Deadline")):
        fact = plan.get(key)
        lines.append(
            f"| {label} | {_cell(fact['value']) if fact else 'Not confirmed'} | "
            f"{_cell(fact['evidence']) if fact else '-'} |"
        )
    for key, label in (
        ("deliverables", "Deliverables"),
        ("acceptance_criteria", "Definition of done"),
        ("dependencies", "Dependencies"),
    ):
        facts = plan.get(key) or []
        values = "<br>".join(_cell(item["value"]) for item in facts) or "Not confirmed"
        evidence = "<br>".join(_cell(item["evidence"]) for item in facts) or "-"
        lines.append(f"| {label} | {values} | {evidence} |")

    lines.extend(["", "## Open commitments"])
    if missing:
        lines.extend(f"- [ ] {item}" for item in missing)
    else:
        lines.append("- No required commitment is missing from the supplied context.")

    lines.extend(["", "## Proposed next steps", "", "| # | Action | Owner | Timing |", "|---:|---|---|---|"])
    steps = plan.get("next_steps") or []
    if steps:
        for index, step in enumerate(steps, 1):
            lines.append(
                f"| {index} | {_cell(step['action'])} | {_cell(step['owner'])} | {_cell(step['timing'])} |"
            )
    else:
        lines.append("| 1 | Resolve the open commitments before execution | TBD | Next review |")

    lines.extend(["", "## Risks and assumptions"])
    risks = plan.get("risks") or []
    if risks:
        for risk in risks:
            label = "confirmed" if risk["kind"] == "stated" else "inferred - verify"
            lines.append(f"- **{label}:** {risk['value']}")
    else:
        lines.append("- No risks were identified from the supplied context.")

    auto_questions = {
        "owner": "Who is the directly responsible owner?",
        "deadline": "What is the deadline or next review date?",
        "deliverables": "What exact artifact or outcome must be delivered?",
        "acceptance_criteria": "How will the team decide this action is done?",
        "dependencies": "What dependencies or approvals can block this action?",
    }
    questions = list(plan.get("questions") or [])
    for key, question in auto_questions.items():
        if not plan.get(key) and question not in questions:
            questions.append(question)
    lines.extend(["", "## Questions to close"])
    lines.extend(f"- {question}" for question in questions[:8])
    if not questions:
        lines.append("- No clarification question is required.")

    lines.extend(["", "---", "Generated by ActionGate. Proposed steps and inferred risks require human approval."])
    return "\n".join(lines)


def _render_html(title: str, plan: dict[str, Any]) -> str:
    score = _readiness_score(plan)
    missing = _missing_fields(plan)
    if not missing:
        status, color = "GREEN - READY", "#137333"
    elif score >= 50:
        status, color = "YELLOW - NEEDS CLARIFICATION", "#8a5a00"
    else:
        status, color = "RED - BLOCKED", "#b3261e"

    def fact_row(label: str, key: str) -> str:
        fact = plan.get(key)
        value = escape(fact["value"], quote=True) if fact else "Not confirmed"
        evidence = escape(fact["evidence"], quote=True) if fact else "-"
        return f"<tr><th>{label}</th><td>{value}</td><td>{evidence}</td></tr>"

    rows = "".join(fact_row(label, key) for key, label in (
        ("objective", "Objective"),
        ("owner", "Owner"),
        ("deadline", "Deadline"),
    ))
    for key, label in (
        ("deliverables", "Deliverables"),
        ("acceptance_criteria", "Definition of done"),
        ("dependencies", "Dependencies"),
    ):
        facts = plan.get(key) or []
        values = "<br>".join(escape(item["value"], quote=True) for item in facts) or "Not confirmed"
        evidence = "<br>".join(escape(item["evidence"], quote=True) for item in facts) or "-"
        rows += f"<tr><th>{label}</th><td>{values}</td><td>{evidence}</td></tr>"

    open_items = "".join(f"<li>{escape(item, quote=True)}</li>" for item in missing)
    if not open_items:
        open_items = "<li>No required commitment is missing.</li>"
    questions = "".join(
        f"<li>{escape(item, quote=True)}</li>" for item in (plan.get("questions") or [])[:8]
    ) or "<li>No additional model-generated question.</li>"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>ActionGate</title></head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:24px auto;color:#202124">
<header style="border-left:8px solid {color};padding:12px 18px;background:#f8f9fa">
<h1 style="margin:0 0 8px">ActionGate: {escape(title, quote=True)}</h1>
<strong style="color:{color}">{score}/100 - {status}</strong></header>
<p>Only source-backed claims appear as confirmed facts.</p>
<table style="width:100%;border-collapse:collapse" border="1" cellpadding="8">
<thead><tr><th>Field</th><th>Confirmed value</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Open commitments</h2><ul>{open_items}</ul>
<h2>Questions to close</h2><ul>{questions}</ul>
<p><small>Proposed work requires human approval.</small></p>
</body></html>"""


def _source_text(input: AgentInput) -> str:
    task = input.task
    attendees = ", ".join(str(a.get("name")) for a in input.attendees if a.get("name"))
    return (
        f"Task title: {task.get('title') or ''}\n"
        f"Task description: {task.get('description') or ''}\n"
        f"Meeting summary: {input.summary}\n"
        f"Meeting attendees: {attendees}"
    )


async def handler(input: AgentInput, ctx: Ctx) -> dict[str, Any]:
    title = str(input.task.get("title") or "Untitled action").strip()
    source = _source_text(input)
    prompt = f"Analyze this meeting action. Return JSON only using this schema:\n{SCHEMA}\n\nSOURCE:\n{source}"

    try:
        ctx.log("extracting an evidence-backed execution contract")
        raw_draft = await ctx.llm.complete(system=SYSTEM_PROMPT, prompt=prompt, temperature=0.1)
        draft = _extract_json(raw_draft)
    except Exception as exc:  # The endpoint should still return a useful artifact.
        ctx.log(f"structured extraction failed: {type(exc).__name__}")
        draft = {"objective": {"value": title, "evidence": title}, "questions": []}

    try:
        ctx.log("running independent hallucination and completeness review")
        review_prompt = (
            f"Review the candidate against the source. Remove or correct every factual claim whose evidence "
            f"is not an exact quote. Improve proposed next steps and clarification questions. Return JSON only "
            f"with the same schema.\n\nSCHEMA:\n{SCHEMA}\n\nSOURCE:\n{source}\n\nCANDIDATE:\n"
            f"{json.dumps(draft, ensure_ascii=False)}"
        )
        reviewed_raw = await ctx.llm.complete(system=SYSTEM_PROMPT, prompt=review_prompt, temperature=0.0)
        reviewed = _extract_json(reviewed_raw)
    except Exception as exc:
        ctx.log(f"review pass failed; using audited draft: {type(exc).__name__}")
        reviewed = draft

    audited = _audit_plan(reviewed, source)
    report = _render(title, audited)
    html_report = _render_html(title, audited)
    ctx.log(f"readiness={_readiness_score(audited)} missing={len(_missing_fields(audited))}")
    return {
        "artifacts": [
            {"type": "markdown", "title": f"ActionGate - {title}", "content": report},
            {"type": "html", "title": f"ActionGate visual report - {title}", "content": html_report},
        ]
    }
