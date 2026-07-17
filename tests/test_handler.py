import json

import pytest

from handler import (
    _audit_plan,
    _deterministic_contract,
    _extract_json,
    _render,
    _render_html,
    handler,
)
from sitrep_agent.sdk import AgentInput, Ctx


SOURCE = """Task title: Follow up with Acme about the pilot next week
Task description:
Meeting summary: Acme wants a security review. Jordan said legal needs two business days.
Meeting attendees: Maya Chen, Jordan Lee"""


def fact(value: str, evidence: str) -> dict[str, str]:
    return {"value": value, "evidence": evidence}


def test_extract_json_accepts_fenced_output():
    assert _extract_json('```json\n{"questions": []}\n```') == {"questions": []}


def test_attendee_name_is_not_accepted_as_owner():
    plan = {"owner": fact("Maya Chen", "Maya Chen")}
    assert _audit_plan(plan, SOURCE)["owner"] is None


@pytest.mark.parametrize(
    "evidence",
    ["Maya attended the meeting", "Maya said Jordan owns the launch plan"],
)
def test_person_mention_is_not_accepted_as_owner(evidence: str):
    source = SOURCE + f"\nAdditional note: {evidence}"
    assert _audit_plan({"owner": fact("Maya", evidence)}, source)["owner"] is None


@pytest.mark.parametrize(
    ("value", "evidence"),
    [
        ("Maya", "Owner: Maya"),
        ("Maya", "Maya is responsible for the launch plan"),
        ("Maya", "The launch plan was assigned to Maya"),
    ],
)
def test_direct_assignment_is_accepted_as_owner(value: str, evidence: str):
    source = SOURCE + f"\nAdditional note: {evidence}"
    assert _audit_plan({"owner": fact(value, evidence)}, source)["owner"]["value"] == value


@pytest.mark.parametrize("deadline", ["next week", "Friday", "tomorrow at 3 PM", "ASAP"])
def test_vague_deadline_is_not_execution_ready(deadline: str):
    plan = {"deadline": fact(deadline, "next week" if deadline == "next week" else deadline)}
    source = SOURCE + f"\nAdditional note: {deadline}"
    assert _audit_plan(plan, source)["deadline"] is None


def test_unsupported_fact_is_removed():
    plan = {"deliverables": [fact("Signed security packet", "security packet was approved")]}
    assert _audit_plan(plan, SOURCE)["deliverables"] == []


def test_supported_evidence_cannot_validate_an_invented_value():
    plan = {
        "deliverables": [
            fact("Signed SOC2 packet approved", "Priya mentioned the SOC2 packet may be outdated")
        ]
    }
    source = SOURCE + " Priya mentioned the SOC2 packet may be outdated"
    assert _audit_plan(plan, source)["deliverables"] == []


@pytest.mark.parametrize("deadline", ["in 2 weeks", "Q3", "next 30 days", "EOD"])
def test_relative_or_underspecified_numeric_deadline_is_rejected(deadline: str):
    source = SOURCE + f"\nAdditional note: {deadline}"
    assert _audit_plan({"deadline": fact(deadline, deadline)}, source)["deadline"] is None


def test_absolute_deadline_is_accepted():
    deadline = "2026-07-20 17:00 KST"
    evidence = f"Deadline: {deadline}"
    source = SOURCE + f"\nAdditional note: {evidence}"
    assert _audit_plan({"deadline": fact(deadline, evidence)}, source)["deadline"]["value"] == deadline


@pytest.mark.parametrize(
    ("deadline", "evidence"),
    [
        ("2026-07-20", "Deadline: 2026-07-20"),
        ("2026-02-30 17:00 KST", "Deadline: 2026-02-30 17:00 KST"),
        ("2026-07-20 17:00 KST", "Do not start before 2026-07-20 17:00 KST"),
    ],
)
def test_non_actionable_date_is_not_accepted_as_deadline(deadline: str, evidence: str):
    source = SOURCE + f"\nAdditional note: {evidence}"
    assert _audit_plan({"deadline": fact(deadline, evidence)}, source)["deadline"] is None


def test_unrelated_evidence_cannot_confirm_a_risk():
    risk = {
        "value": "Customer approved production rollout",
        "evidence": "Legal needs two business days",
        "kind": "stated",
    }
    source = SOURCE + "\nLegal needs two business days"
    audited = _audit_plan({"risks": [risk]}, source)

    assert audited["risks"][0]["kind"] == "inferred"
    assert "**confirmed:**" not in _render("Pilot", audited)


def test_exact_risk_evidence_remains_confirmed_and_visible():
    evidence = "Legal review may delay launch"
    source = SOURCE + f"\nAdditional note: {evidence}"
    audited = _audit_plan(
        {"risks": [{"value": evidence, "evidence": evidence, "kind": "stated"}]}, source
    )

    assert audited["risks"][0]["kind"] == "stated"
    assert f'evidence: "{evidence}"' in _render("Pilot", audited)


def test_green_requires_every_contract_field():
    plan = {
        "objective": fact("Ship pilot", "Ship pilot"),
        "owner": fact("Maya", "Maya owns the pilot"),
        "deadline": fact("2026-07-20 17:00 KST", "Deadline: 2026-07-20 17:00 KST"),
        "deliverables": [fact("Rollout plan", "Rollout plan")],
        "acceptance_criteria": [fact("Approved by Acme", "Approved by Acme")],
        "dependencies": [fact("Legal review", "Legal review")],
    }
    source = " ".join(item["evidence"] for key in plan.values() for item in (key if isinstance(key, list) else [key]))
    audited = _audit_plan(plan, f"Task title: {source}\nMeeting attendees:")
    assert "GREEN - READY" in _render("Pilot", audited)

    plan.pop("acceptance_criteria")
    audited = _audit_plan(plan, f"Task title: {source}\nMeeting attendees:")
    assert "GREEN - READY" not in _render("Pilot", audited)


def test_html_contains_the_same_actionable_sections_as_markdown():
    plan = {
        "objective": fact("Ship pilot", "Ship pilot"),
        "risks": [{"value": "Legal review may delay launch", "kind": "inferred", "evidence": ""}],
        "next_steps": [{"action": "Confirm owner", "owner": "TBD", "timing": "TBD"}],
        "questions": [],
    }
    audited = _audit_plan(plan, "Task title: Ship pilot\nMeeting attendees: Maya")
    html = _render_html("Pilot <script>alert(1)</script>", audited)

    assert "What happens next" in html
    assert "Who is the directly responsible owner?" in html
    assert "Proposed next steps" in html
    assert "Legal review may delay launch" in html
    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html


def test_resolved_contract_produces_proceed_packet():
    plan = {
        "objective": fact("Send the rollout plan", "Send the rollout plan"),
        "owner": fact("Maya", "Maya owns the follow-up"),
        "deadline": fact("2026-07-20 17:00 KST", "Due 2026-07-20 17:00 KST"),
        "deliverables": [fact("rollout plan", "Send the rollout plan")],
        "acceptance_criteria": [fact("approved by Acme", "Done when approved by Acme")],
        "dependencies": [fact("legal approval", "Depends on legal approval")],
        "questions": [],
    }
    source = "\n".join(
        [
            "Task title: Send the rollout plan",
            "Task description: Maya owns the follow-up. Due 2026-07-20 17:00 KST.",
            "Meeting summary: Done when approved by Acme. Depends on legal approval.",
            "Meeting attendees: Maya",
        ]
    )
    audited = _audit_plan(plan, source)
    markdown = _render("Acme rollout", audited)

    assert "GREEN - READY" in markdown
    assert "Decision: PROCEED" in markdown
    assert "fully specified and ready to hand off" in markdown


def test_deterministic_contract_extracts_only_explicit_labeled_commitments():
    source = """Task title: Ship Acme rollout plan
Task description: Maya will deliver the Acme rollout plan by 2026-07-20 17:00 KST.
Meeting summary: Objective: Ship Acme rollout plan. Maya owns the rollout plan. Deadline: 2026-07-20 17:00 KST. Deliverable: Acme rollout plan. Definition of done: Acme approves the rollout plan. Dependency: legal approval.
Meeting attendees: Maya"""
    audited = _audit_plan(_deterministic_contract("Ship Acme rollout plan", source), source)

    assert audited["owner"]["value"] == "Maya"
    assert audited["deadline"]["value"] == "2026-07-20 17:00 KST"
    assert audited["deliverables"][0]["value"] == "Acme rollout plan"
    assert audited["acceptance_criteria"][0]["value"] == "Acme approves the rollout plan"
    assert audited["dependencies"][0]["value"] == "legal approval"


class FakeLLM:
    model = "fake"

    def __init__(self, responses: list[dict]):
        self.responses = [json.dumps(item) for item in responses]

    async def complete(self, **_kwargs) -> str:
        return self.responses.pop(0)


class FailingLLM:
    model = "failing"

    async def complete(self, **_kwargs) -> str:
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_handler_returns_audited_contract_and_questions():
    draft = {
        "objective": fact("Follow up with Acme", "Follow up with Acme"),
        "owner": fact("Maya Chen", "Maya Chen"),
        "deadline": fact("next week", "next week"),
        "deliverables": [],
        "acceptance_criteria": [],
        "dependencies": [fact("Legal review", "legal needs two business days")],
        "risks": [{"value": "Legal review could delay delivery", "evidence": "legal needs two business days", "kind": "stated"}],
        "next_steps": [{"action": "Confirm the owner and exact deadline", "owner": "TBD", "timing": "Now"}],
        "questions": ["Who owns the Acme follow-up?"],
    }
    agent_input = AgentInput(
        task={"title": "Follow up with Acme about the pilot next week"},
        summary="Acme wants a security review. Jordan said legal needs two business days.",
        attendees=[{"name": "Maya Chen"}, {"name": "Jordan Lee"}],
        agent={},
    )
    ctx = Ctx(instructions="", tools=[], llm=FakeLLM([draft]))

    result = await handler(agent_input, ctx)

    content = result["artifacts"][0]["content"]
    assert "RED - BLOCKED" in content or "YELLOW - NEEDS CLARIFICATION" in content
    assert "Who is the directly responsible owner?" in content
    assert "What is the calendar deadline or review date, including timezone?" in content
    assert "| Owner | Not confirmed | - |" in content
    assert "| 1 | Confirm the owner and exact deadline | TBD | TBD |" in content
    assert "Copy-ready clarification request" in content
    assert [item["type"] for item in result["artifacts"]] == ["markdown", "html"]
    assert "<script" not in result["artifacts"][1]["content"]
    assert len(ctx.logs) == 2


@pytest.mark.asyncio
async def test_provider_failure_returns_a_safe_hold_packet():
    agent_input = AgentInput(
        task={"title": "Prepare the launch plan"},
        summary="",
        attendees=[{"name": "Maya Chen"}],
        agent={},
    )
    ctx = Ctx(instructions="", tools=[], llm=FailingLLM())

    result = await handler(agent_input, ctx)

    markdown = result["artifacts"][0]["content"]
    assert "HOLD" in markdown
    assert "Who is the directly responsible owner?" in markdown
    assert "Maya Chen" not in markdown
    assert "structured extraction failed" in ctx.logs[1]


@pytest.mark.asyncio
async def test_provider_failure_still_proceeds_for_explicit_complete_contract():
    agent_input = AgentInput(
        task={
            "title": "Ship Acme rollout plan",
            "description": "Maya will deliver the Acme rollout plan by 2026-07-20 17:00 KST.",
        },
        summary=(
            "Objective: Ship Acme rollout plan. Maya owns the rollout plan. "
            "Deadline: 2026-07-20 17:00 KST. Deliverable: Acme rollout plan. "
            "Definition of done: Acme approves the rollout plan. Dependency: legal approval."
        ),
        attendees=[{"name": "Maya"}],
        agent={},
    )
    ctx = Ctx(instructions="", tools=[], llm=FailingLLM())

    result = await handler(agent_input, ctx)

    markdown = result["artifacts"][0]["content"]
    assert "GREEN - READY" in markdown
    assert "Decision: PROCEED" in markdown
    assert "Verified commitments: 6/6" in markdown
