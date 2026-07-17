import json

from scripts.evaluate_actiongate import DEFAULT_CASES, evaluate, render_markdown, summarize


def test_adversarial_suite_eliminates_false_proceed_and_risk_errors():
    cases = json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))
    results = evaluate(cases)
    summary = summarize(results)

    assert summary["naive"] == {
        "correct": 3,
        "false_proceed": 5,
        "false_hold": 0,
        "risk_errors": 1,
    }
    assert summary["actiongate"] == {
        "correct": 8,
        "false_proceed": 0,
        "false_hold": 0,
        "risk_errors": 0,
    }


def test_evaluation_report_is_judge_readable():
    cases = json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))
    report = render_markdown(evaluate(cases))

    assert "False PROCEED" in report
    assert "Presence-only baseline" in report
    assert "ActionGate | 8/8 | 0 | 0 | 0" in report
