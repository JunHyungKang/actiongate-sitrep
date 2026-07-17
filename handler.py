"""ActionGate: turn a meeting action into an evidence-backed execution contract."""
from __future__ import annotations

import json
import re
from datetime import datetime
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

FIELD_SPECS = (
    ("objective", "Objective", 20),
    ("owner", "Directly responsible owner", 20),
    ("deadline", "Deadline or review date", 15),
    ("deliverables", "Concrete deliverables", 15),
    ("acceptance_criteria", "Measurable definition of done", 20),
    ("dependencies", "Dependencies or explicit none", 10),
)

AUTO_QUESTIONS = {
    "objective": "What exact outcome should this action produce?",
    "owner": "Who is the directly responsible owner?",
    "deadline": "What is the calendar deadline or review date, including timezone?",
    "deliverables": "What exact artifact or outcome must be delivered?",
    "acceptance_criteria": "How will the team decide this action is done?",
    "dependencies": "What dependencies or approvals can block this action, or are there none?",
}


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


def _supported_owner(value: Any, source: str) -> dict[str, str] | None:
    fact = _supported_fact(value, source)
    if not fact:
        return None
    owner = re.escape(_normalize(fact["value"]))
    evidence = _normalize(fact["evidence"])
    ownership_patterns = (
        rf"\b(?:owner|assignee|responsible person)\s*(?:is|:|-)\s*{owner}\b",
        rf"\b(?:assigned|assign)\s+to\s+{owner}\b",
        rf"\b{owner}\s+(?:owns\b|is\s+(?:the\s+)?(?:owner|assignee)\b|"
        rf"is\s+responsible\b|will\s+(?:deliver|prepare|complete|send|create|update|lead|coordinate)\b)",
        rf"\bresponsibility\s+(?:belongs\s+to|lies\s+with)\s+{owner}\b",
    )
    return fact if any(re.search(pattern, evidence) for pattern in ownership_patterns) else None


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
    evidence = _normalize(fact["evidence"])
    iso_date = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", value)
    time_pattern = r"\b(?:(?:[01]?\d|2[0-3]):[0-5]\d(?:\s*(?:am|pm))?|\d{1,2}(?::[0-5]\d)?\s*(?:am|pm))\b"
    timezone_pattern = r"\b(?:utc|gmt|kst|jst|est|edt|cst|cdt|mst|mdt|pst|pdt|cet|cest|aest|aedt)\b|[+-]\d{2}:?\d{2}\b"
    deadline_semantics = (
        r"\b(?:deadline|due|review date)\b",
        r"\b(?:deliver|complete|finish|send|submit)(?:ed)?\s+by\b",
        r"\bby\s+20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\b",
    )
    negative_semantics = ("not before", "do not start before", "starts on", "starts at")
    if (
        any(term in value for term in relative_terms)
        or any(re.search(pattern, value) for pattern in relative_patterns)
        or not iso_date
        or not re.search(time_pattern, value)
        or not re.search(timezone_pattern, value)
        or any(term in evidence for term in negative_semantics)
        or not any(re.search(pattern, evidence) for pattern in deadline_semantics)
    ):
        return None
    try:
        datetime(int(iso_date.group(1)), int(iso_date.group(2)), int(iso_date.group(3)))
    except ValueError:
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


def _first_match(source: str, patterns: tuple[str, ...]) -> dict[str, str] | None:
    for pattern in patterns:
        if match := re.search(pattern, source, re.IGNORECASE | re.MULTILINE):
            value = match.group("value").strip(" \t.\n")
            evidence = match.group(0).strip()
            if value:
                return {"value": value, "evidence": evidence}
    return None


def _deterministic_contract(title: str, source: str) -> dict[str, Any]:
    """Recover explicit commitments when the optional LLM is unavailable."""
    owner = _first_match(
        source,
        (
            r"\b(?:owner|assignee|responsible person)\s*(?:is|:|-)\s*(?P<value>[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,2})\b",
            r"\b(?P<value>[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,2})\s+(?:owns\b|is\s+(?:the\s+)?(?:owner|assignee)\b|is\s+responsible\b)",
            r"\b(?:assigned|assign)\s+to\s+(?P<value>[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,2})\b",
        ),
    )
    deadline = _first_match(
        source,
        (
            r"\b(?:deadline|due|review date)\s*:\s*(?P<value>20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\s+(?:(?:[01]?\d|2[0-3]):[0-5]\d|\d{1,2}(?::[0-5]\d)?\s*(?:am|pm))\s*(?:UTC|GMT|KST|JST|EST|EDT|CST|CDT|MST|MDT|PST|PDT|CET|CEST|AEST|AEDT|[+-]\d{2}:?\d{2}))\b",
            r"\b(?:deliver|complete|finish|send|submit)(?:ed)?\s+by\s+(?P<value>20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\s+(?:(?:[01]?\d|2[0-3]):[0-5]\d|\d{1,2}(?::[0-5]\d)?\s*(?:am|pm))\s*(?:UTC|GMT|KST|JST|EST|EDT|CST|CDT|MST|MDT|PST|PDT|CET|CEST|AEST|AEDT|[+-]\d{2}:?\d{2}))\b",
        ),
    )

    def labeled_list(label: str) -> list[dict[str, str]]:
        fact = _first_match(source, (rf"\b{label}\s*:\s*(?P<value>[^.\n]+)",))
        return [fact] if fact else []

    deliverables = labeled_list(r"deliverable")
    acceptance = labeled_list(r"(?:definition of done|acceptance criteria)")
    dependencies = labeled_list(r"(?:dependency|dependencies)")
    objective = _first_match(source, (r"\bobjective\s*:\s*(?P<value>[^.\n]+)",)) or {
        "value": title,
        "evidence": title,
    }
    next_steps: list[dict[str, str]] = []
    if owner and deadline and deliverables:
        next_steps.append(
            {
                "action": f"Deliver {deliverables[0]['value']}",
                "owner": owner["value"],
                "timing": deadline["value"],
            }
        )
    return {
        "objective": objective,
        "owner": owner,
        "deadline": deadline,
        "deliverables": deliverables,
        "acceptance_criteria": acceptance,
        "dependencies": dependencies,
        "risks": [],
        "next_steps": next_steps,
        "questions": [],
    }


def _merge_audited(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary)
    for key in ("objective", "owner", "deadline"):
        if not merged.get(key):
            merged[key] = fallback.get(key)
    for key in ("deliverables", "acceptance_criteria", "dependencies"):
        items = list(merged.get(key) or [])
        seen = {(_normalize(item["value"]), _normalize(item["evidence"])) for item in items}
        for item in fallback.get(key) or []:
            identity = (_normalize(item["value"]), _normalize(item["evidence"]))
            if identity not in seen:
                items.append(item)
                seen.add(identity)
        merged[key] = items
    if not merged.get("next_steps"):
        merged["next_steps"] = fallback.get("next_steps") or []
    return merged


def _audit_plan(plan: dict[str, Any], source: str) -> dict[str, Any]:
    # Being listed as an attendee is not evidence that a person owns the action.
    action_source = "\n".join(
        line for line in source.splitlines() if not line.startswith("Meeting attendees:")
    )
    audited: dict[str, Any] = {
        "objective": _supported_fact(plan.get("objective"), source),
        "owner": _supported_owner(plan.get("owner"), action_source),
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
        if kind == "stated" and (supported := _supported_fact(item, source)):
            risks.append({**supported, "kind": "stated"})
        else:
            risks.append(
                {"value": str(item["value"]).strip(), "kind": "inferred", "evidence": ""}
            )
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
    return [label for key, label, _weight in FIELD_SPECS if not plan.get(key)]


def _readiness_score(plan: dict[str, Any]) -> int:
    return sum(weight for key, _label, weight in FIELD_SPECS if plan.get(key))


def _gate(plan: dict[str, Any]) -> tuple[str, str, str]:
    score = _readiness_score(plan)
    if not _missing_fields(plan):
        return "GREEN - READY", "PROCEED", "#137333"
    if score >= 50:
        return "YELLOW - NEEDS CLARIFICATION", "HOLD", "#8a5a00"
    return "RED - BLOCKED", "HOLD", "#b3261e"


def _questions(plan: dict[str, Any]) -> list[str]:
    questions = list(plan.get("questions") or [])
    for key, question in AUTO_QUESTIONS.items():
        if not plan.get(key) and question not in questions:
            questions.append(question)
    return questions[:8]


def _clarification_request(title: str, plan: dict[str, Any]) -> str:
    questions = _questions(plan)
    if not questions:
        return f"{title} is fully specified and ready to hand off."
    lines = [
        f"Before work starts on '{title}', please confirm:",
        *(f"{index}. {question}" for index, question in enumerate(questions, 1)),
        "Once confirmed, the action can move to execution without hidden assumptions.",
    ]
    return "\n".join(lines)


def _cell(value: str) -> str:
    return escape(value, quote=True).replace("|", "\\|").replace("\n", " ").strip()


def _render(title: str, plan: dict[str, Any]) -> str:
    score = _readiness_score(plan)
    missing = _missing_fields(plan)
    status, decision, _color = _gate(plan)
    confirmed_count = len(FIELD_SPECS) - len(missing)

    lines = [
        f"# ActionGate: {title}",
        "",
        f"**Execution readiness: {score}/100 - {status}**",
        f"**Decision: {decision} | Verified commitments: {confirmed_count}/{len(FIELD_SPECS)}**",
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
            evidence = f" - evidence: \"{_cell(risk['evidence'])}\"" if risk["kind"] == "stated" else ""
            lines.append(f"- **{label}:** {risk['value']}{evidence}")
    else:
        lines.append("- No risks were identified from the supplied context.")

    questions = _questions(plan)
    lines.extend(["", "## Questions to close"])
    lines.extend(f"- {question}" for question in questions)
    if not questions:
        lines.append("- No clarification question is required.")

    lines.extend(["", "## Copy-ready clarification request", ""])
    lines.extend(f"> {_cell(line)}" for line in _clarification_request(title, plan).splitlines())

    lines.extend(["", "---", "Generated by ActionGate. Proposed steps and inferred risks require human approval."])
    return "\n".join(lines)


def _render_html(title: str, plan: dict[str, Any]) -> str:
    score = _readiness_score(plan)
    missing = _missing_fields(plan)
    status, decision, color = _gate(plan)
    confirmed_count = len(FIELD_SPECS) - len(missing)

    def fact_row(label: str, key: str) -> str:
        fact = plan.get(key)
        value = escape(fact["value"], quote=True) if fact else "Not confirmed"
        evidence = escape(fact["evidence"], quote=True) if fact else "-"
        return (
            "<tr>"
            f'<th style="text-align:left;padding:10px;border-bottom:1px solid #e7e9ee">{label}</th>'
            f'<td style="padding:10px;border-bottom:1px solid #e7e9ee">{value}</td>'
            f'<td style="padding:10px;border-bottom:1px solid #e7e9ee">{evidence}</td>'
            "</tr>"
        )

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
        rows += (
            "<tr>"
            f'<th style="text-align:left;padding:10px;border-bottom:1px solid #e7e9ee">{label}</th>'
            f'<td style="padding:10px;border-bottom:1px solid #e7e9ee">{values}</td>'
            f'<td style="padding:10px;border-bottom:1px solid #e7e9ee">{evidence}</td>'
            "</tr>"
        )

    open_items = "".join(f"<li>{escape(item, quote=True)}</li>" for item in missing)
    if not open_items:
        open_items = "<li>No required commitment is missing.</li>"
    questions = "".join(f"<li>{escape(item, quote=True)}</li>" for item in _questions(plan))
    if not questions:
        questions = "<li>No clarification question is required.</li>"

    steps = plan.get("next_steps") or []
    step_rows = "".join(
        "<tr>"
        f"<td>{index}</td>"
        f"<td>{escape(step['action'], quote=True)}</td>"
        f"<td>{escape(step['owner'], quote=True)}</td>"
        f"<td>{escape(step['timing'], quote=True)}</td>"
        "</tr>"
        for index, step in enumerate(steps, 1)
    )
    if not step_rows:
        step_rows = (
            "<tr><td>1</td><td>Resolve the open commitments before execution</td>"
            "<td>TBD</td><td>After clarification</td></tr>"
        )

    risks = plan.get("risks") or []
    risk_items = "".join(
        f"<li><strong>{'Confirmed' if risk['kind'] == 'stated' else 'Inferred - verify'}:</strong> "
        f"{escape(risk['value'], quote=True)}"
        f"{' — evidence: &quot;' + escape(risk['evidence'], quote=True) + '&quot;' if risk['kind'] == 'stated' else ''}</li>"
        for risk in risks
    ) or "<li>No risks were identified from the supplied context.</li>"

    clarification = escape(_clarification_request(title, plan), quote=True)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ActionGate execution packet</title></head>
<body style="margin:0;background:#f3f4f6;color:#16181d;font-family:Inter,Arial,sans-serif;line-height:1.5;overflow-wrap:anywhere">
<main style="width:100%;max-width:960px;margin:0 auto;background:#ffffff;box-sizing:border-box">
<header style="padding:28px clamp(16px,5vw,32px) 24px;border-top:8px solid {color};border-bottom:1px solid #d9dde5">
<div style="font-size:12px;font-weight:700;text-transform:uppercase;color:#525866">Execution control</div>
<h1 style="font-size:26px;line-height:1.25;margin:6px 0 18px">{escape(title, quote=True)}</h1>
<div style="display:flex;gap:24px;flex-wrap:wrap;align-items:flex-end">
<div><div style="font-size:12px;color:#525866">Decision</div><strong style="font-size:22px;color:{color}">{decision}</strong></div>
<div><div style="font-size:12px;color:#525866">Readiness</div><strong style="font-size:22px">{score}/100</strong></div>
<div><div style="font-size:12px;color:#525866">Verified</div><strong style="font-size:22px">{confirmed_count}/{len(FIELD_SPECS)}</strong></div>
</div>
<div style="height:8px;background:#e7e9ee;margin-top:20px"><div style="width:{score}%;height:8px;background:{color}"></div></div>
<div style="margin-top:10px;font-weight:700;color:{color}">{status}</div>
</header>
<section style="padding:24px clamp(16px,5vw,32px);border-bottom:1px solid #d9dde5">
<h2 style="font-size:18px;margin:0 0 10px">What happens next</h2>
<div style="white-space:pre-line;background:#f7f8fa;border-left:4px solid {color};padding:16px">{clarification}</div>
</section>
<section style="padding:24px clamp(16px,5vw,32px);border-bottom:1px solid #d9dde5;overflow-x:auto">
<h2 style="font-size:18px;margin:0 0 12px">Verified execution contract</h2>
<table style="width:100%;border-collapse:collapse;font-size:14px">
<thead><tr style="background:#f3f4f6"><th style="text-align:left;padding:10px">Field</th><th style="text-align:left;padding:10px">Confirmed value</th><th style="text-align:left;padding:10px">Source evidence</th></tr></thead>
<tbody>{rows}</tbody></table>
</section>
<section style="padding:24px clamp(16px,5vw,32px);border-bottom:1px solid #d9dde5">
<h2 style="font-size:18px;margin:0 0 8px">Open commitments</h2><ul style="margin:0;padding-left:20px">{open_items}</ul>
<h2 style="font-size:18px;margin:22px 0 8px">Questions to close</h2><ol style="margin:0;padding-left:20px">{questions}</ol>
</section>
<section style="padding:24px clamp(16px,5vw,32px);border-bottom:1px solid #d9dde5;overflow-x:auto">
<h2 style="font-size:18px;margin:0 0 12px">Proposed next steps</h2>
<table style="width:100%;border-collapse:collapse;font-size:14px">
<thead><tr style="background:#f3f4f6"><th style="padding:10px;text-align:left">#</th><th style="padding:10px;text-align:left">Action</th><th style="padding:10px;text-align:left">Owner</th><th style="padding:10px;text-align:left">Timing</th></tr></thead>
<tbody>{step_rows}</tbody></table>
<h2 style="font-size:18px;margin:22px 0 8px">Risks and assumptions</h2><ul style="margin:0;padding-left:20px">{risk_items}</ul>
</section>
<footer style="padding:18px clamp(16px,5vw,32px);color:#525866;font-size:12px">ActionGate confirms only source-backed facts. Proposed steps and inferred risks require human approval.</footer>
</main>
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
    deterministic_audited = _audit_plan(_deterministic_contract(title, source), source)

    if not _missing_fields(deterministic_audited):
        ctx.log("explicit contract complete; skipping LLM extraction")
        audited = deterministic_audited
    else:
        try:
            ctx.log("extracting an evidence-backed execution contract")
            raw_draft = await ctx.llm.complete(system=SYSTEM_PROMPT, prompt=prompt, temperature=0.1)
            draft = _extract_json(raw_draft)
        except Exception as exc:  # The endpoint should still return a useful artifact.
            ctx.log(f"structured extraction failed: {type(exc).__name__}")
            draft = {"objective": {"value": title, "evidence": title}, "questions": []}
        audited = _merge_audited(_audit_plan(draft, source), deterministic_audited)
    report = _render(title, audited)
    html_report = _render_html(title, audited)
    ctx.log(f"readiness={_readiness_score(audited)} missing={len(_missing_fields(audited))}")
    return {
        "artifacts": [
            {"type": "markdown", "title": f"ActionGate audit trail - {title}", "content": report},
            {"type": "html", "title": f"ActionGate approval packet - {title}", "content": html_report},
        ]
    }
