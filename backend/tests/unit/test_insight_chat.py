"""tests/unit/test_insight_chat.py — OG-051 unanswerable-question detection."""

from __future__ import annotations

from agents.insight_chat import is_unanswerable


class TestIsUnanswerable:
    def test_decline_phrase_detected(self) -> None:
        assert is_unanswerable("I don't have that data yet.") is True

    def test_case_insensitive(self) -> None:
        assert is_unanswerable("Sorry, I DON'T HAVE that on file.") is True

    def test_normal_answer_is_answerable(self) -> None:
        assert is_unanswerable("You had 42 fit-checks this week, 12 resulted in a size change.") is False
