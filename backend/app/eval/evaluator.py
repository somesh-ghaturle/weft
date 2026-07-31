"""Pluggable scoring interface: score(item, output) -> EvalResult.

Kept deliberately narrow so Phase 3's RAG triad evaluators are additive new
Evaluator implementations, not a rewrite of the eval-run machinery.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class EvalResult:
    score: float
    reasoning: str = ""


class Evaluator(Protocol):
    name: str

    def score(self, item: dict[str, Any], output: Any) -> EvalResult: ...


class ExactMatchEvaluator:
    """1.0 if output equals item['expected_output'] exactly, else 0.0."""

    name = "exact_match"

    def score(self, item: dict[str, Any], output: Any) -> EvalResult:
        expected = item.get("expected_output")
        matched = output == expected
        return EvalResult(score=1.0 if matched else 0.0, reasoning=f"expected={expected!r} output={output!r}")


class RegexEvaluator:
    """1.0 if the string form of output matches the given pattern."""

    name = "regex"

    def __init__(self, pattern: str):
        self._pattern = re.compile(pattern)

    def score(self, item: dict[str, Any], output: Any) -> EvalResult:
        matched = self._pattern.search(str(output)) is not None
        return EvalResult(
            score=1.0 if matched else 0.0,
            reasoning=f"pattern={self._pattern.pattern!r} output={output!r}",
        )


class SchemaValidityEvaluator:
    """1.0 if output (a dict) has all of the given required keys."""

    name = "schema_validity"

    def __init__(self, required_keys: list[str]):
        self._required_keys = required_keys

    def score(self, item: dict[str, Any], output: Any) -> EvalResult:
        if not isinstance(output, dict):
            return EvalResult(score=0.0, reasoning=f"output is not an object: {type(output).__name__}")
        missing = [k for k in self._required_keys if k not in output]
        return EvalResult(
            score=1.0 if not missing else 0.0,
            reasoning="all required keys present" if not missing else f"missing keys: {missing}",
        )


class LLMJudgeNotConfiguredError(RuntimeError):
    pass


class LLMJudgeEvaluator:
    """Scores output using a judge LLM call. Not wired to a provider yet — Phase 2
    ships the interface and score-parsing contract; a real client (OpenAI/Anthropic)
    plugs in via `call_model` once an API key is available."""

    name = "llm_judge"

    def __init__(self, judge_prompt: str, model: str, call_model=None):
        self._judge_prompt = judge_prompt
        self._model = model
        self._call_model = call_model

    def score(self, item: dict[str, Any], output: Any) -> EvalResult:
        if self._call_model is None:
            raise LLMJudgeNotConfiguredError(
                "LLMJudgeEvaluator has no call_model configured — supply a callable "
                "(prompt: str) -> str that invokes your judge model."
            )
        rendered_prompt = self._judge_prompt.format(input=item.get("input"), output=output)
        raw_response = self._call_model(rendered_prompt)
        return _parse_judge_response(raw_response)


def _parse_judge_response(raw_response: str) -> EvalResult:
    """Expects 'SCORE: <0-1 float>\\nREASONING: <text>' from the judge model."""
    score = 0.0
    reasoning = raw_response.strip()
    score_match = re.search(r"SCORE:\s*([0-9.]+)", raw_response)
    reasoning_match = re.search(r"REASONING:\s*(.+)", raw_response, re.DOTALL)
    if score_match:
        score = max(0.0, min(1.0, float(score_match.group(1))))
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()
    return EvalResult(score=score, reasoning=reasoning)
