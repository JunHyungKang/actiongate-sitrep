import asyncio

from scripts.evaluate_scenarios import evaluate, render_markdown, summarize


def test_scenario_suite_protects_final_artifacts():
    results = asyncio.run(evaluate())

    assert summarize(results) == {
        "correct": 6,
        "false_proceed": 0,
        "false_hold": 0,
        "unsupported_confirmed": 0,
        "forbidden_confirmed": 0,
        "questions_found": 14,
        "questions_expected": 14,
        "safe_artifacts": 6,
    }


def test_scenario_report_is_judge_readable():
    report = render_markdown(asyncio.run(evaluate()))

    assert "Decision accuracy | 6/6" in report
    assert "False PROCEED | 0" in report
    assert "Missing-field question recall | 14/14" in report
    assert "Safe, complete artifact pairs | 6/6" in report
