"""
Multi-Strategy Planner
Generates multiple candidate fixes using different strategies:
1. Minimal  — smallest possible change to fix the bug
2. Defensive — adds error handling, type checks, guards
3. Refactored — clean rewrite following best practices
4. Typed — adds type hints and input validation

This diversity increases the chance that at least one fix is correct.
"""

import logging
from llm.groq_client import get_llm
from .memory import CandidateFix

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a world-class Python engineer.
Generate Python bug fixes that are correct, clean, and production-ready.
Respond with valid JSON only. Never add markdown or explanation outside the JSON."""

STRATEGIES = {
    "minimal": {
        "description": "Make the smallest possible change to fix only the reported bug. Do not refactor.",
        "tone": "conservative",
    },
    "defensive": {
        "description": "Fix the bug AND add defensive programming: input validation, try/except, guard clauses, helpful error messages.",
        "tone": "robust",
    },
    "refactored": {
        "description": "Fix the bug AND clean up the code: better naming, structure, readability, PEP 8 compliance.",
        "tone": "clean",
    },
    "typed": {
        "description": "Fix the bug AND add Python type hints and basic docstrings.",
        "tone": "professional",
    },
}


class Planner:
    """
    Generates multiple candidate fixes using diverse strategies.
    Each candidate is independently reasoned about and includes
    confidence scores and explanations.
    """

    def __init__(self):
        self.llm = get_llm()

    def generate_fixes(
        self,
        original_code: str,
        error_analysis: dict,
        reflection: dict,
        strategies: list[str] = None,
        num_candidates: int = 4,
    ) -> list[CandidateFix]:
        """
        Generate multiple fix candidates using different strategies.
        Returns a list of CandidateFix objects.
        """
        selected_strategies = strategies or list(STRATEGIES.keys())
        candidates = []

        for strategy_name in selected_strategies[:num_candidates]:
            strategy = STRATEGIES.get(strategy_name, STRATEGIES["minimal"])
            candidate = self._generate_single_fix(
                original_code=original_code,
                error_analysis=error_analysis,
                reflection=reflection,
                strategy_name=strategy_name,
                strategy=strategy,
            )
            if candidate:
                candidates.append(candidate)

        # Deduplicate by code content
        seen = set()
        unique = []
        for c in candidates:
            key = c.code.strip()
            if key not in seen:
                seen.add(key)
                unique.append(c)

        return unique

    def _generate_single_fix(
        self,
        original_code: str,
        error_analysis: dict,
        reflection: dict,
        strategy_name: str,
        strategy: dict,
    ) -> CandidateFix | None:
        """Generate one candidate fix using the given strategy."""

        avoid_list = "\n".join(
            f"  - {x}" for x in reflection.get("what_to_avoid", [])
        ) or "  - None"

        hints_list = "\n".join(
            f"  - {h}" for h in error_analysis.get("fix_hints", [])
        ) or "  - Fix the reported error"

        prompt = f"""Fix the following buggy Python code using the "{strategy_name}" strategy.

## Strategy: {strategy_name.upper()}
{strategy['description']}

## Buggy Code:
```python
{original_code}
```

## Error Details:
- Error Type: {error_analysis.get('error_category', 'unknown')}
- Plain English: {error_analysis.get('plain_english', '')}
- Root Cause: {error_analysis.get('root_cause', '')}

## Fix Hints:
{hints_list}

## What NOT To Do (learned from previous failed attempts):
{avoid_list}

## New Approach Guidance:
{reflection.get('new_approach', 'Fix the core issue.')}
{f"Key Insight: {reflection['key_insight']}" if reflection.get('key_insight') else ''}

Return a JSON object with exactly these fields:
{{
  "fixed_code": "complete corrected Python code here (not just a snippet)",
  "explanation": "1-3 sentences: what was wrong and what you changed",
  "diff_summary": "Brief description of the specific lines/changes made",
  "confidence": 0.0-1.0,
  "strategy_notes": "Why this strategy is appropriate for this bug"
}}

IMPORTANT:
- fixed_code must be COMPLETE runnable Python code
- fixed_code must use proper Python indentation
- Do not include markdown fences inside fixed_code
- confidence should reflect how certain you are this fix is correct"""

        try:
            result = self.llm.chat_json(
                messages=[{"role": "user", "content": prompt}],
                system=SYSTEM_PROMPT,
                model="default",
                temperature=0.15,
            )

            code = result.get("fixed_code", "").strip()
            # Strip accidental markdown fences
            if code.startswith("```"):
                lines = code.split("\n")
                code = "\n".join(lines[1:])
                if code.endswith("```"):
                    code = code[:-3]

            if not code or len(code) < 5:
                logger.warning(f"Planner returned empty code for strategy {strategy_name}")
                return None

            return CandidateFix(
                strategy=strategy_name,
                code=code.strip(),
                explanation=result.get("explanation", ""),
                confidence=float(result.get("confidence", 0.5)),
                diff_summary=result.get("diff_summary", ""),
            )

        except Exception as e:
            logger.error(f"Planner failed for strategy {strategy_name}: {e}")
            return None

    def generate_test_cases_for_code(self, code: str, error_analysis: dict) -> list[dict]:
        """
        Generate test cases for validating fixes.
        Uses test_cases from error_analysis if available,
        or generates new ones from the code structure.
        """
        # Use pre-generated test cases from error analysis
        existing = error_analysis.get("test_cases", [])
        if existing:
            return existing

        # Generate new ones
        prompt = f"""Analyze this Python code and generate 2-4 simple test cases.

```python
{code[:1000]}
```

Return JSON:
{{
  "test_cases": [
    {{"call": "function_name(args)", "expected": "expected_result_as_string"}}
  ]
}}

Only include test cases where you are CERTAIN what the expected output is.
Use an empty list if the code has no testable functions."""

        try:
            result = self.llm.chat_json(
                messages=[{"role": "user", "content": prompt}],
                system="You are a Python testing expert. Return valid JSON only.",
                model="fast",
                temperature=0.1,
            )
            return result.get("test_cases", [])
        except Exception:
            return []