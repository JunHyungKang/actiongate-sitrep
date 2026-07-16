from pathlib import Path

from scripts.preflight_submission import run_checks, word_count


ROOT = Path(__file__).resolve().parents[1]


def test_word_count_handles_markdown_and_korean() -> None:
    assert word_count("# ActionGate\n\nEvidence-first 실행 계약") == 4


def test_repository_passes_local_submission_preflight() -> None:
    failures = [check for check in run_checks(ROOT) if not check.ok]
    assert failures == []
