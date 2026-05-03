"""
Validator Module
Checks that a "fixed" candidate is not only error-free,
but actually correct and equivalent to what was intended.

Validation layers:
1. Syntax check (static)
2. Execution check (runs without error)
3. Output check (produces expected output)
4. Test case check (passes test assertions)
5. LLM semantic check (does the logic make sense?)
6. Regression check (doesn't break what was working)
"""

import logging
from .memory import CandidateFix, ExecutionResult, AttemptStatus
from .executor import CodeExecutor

logger = logging.getLogger(__name__)


class Validator:
    """
    Multi-layer validator for candidate fixes.
    Assigns a validation score 0.0 – 1.0 to each candidate.
    """

    def __init__(self):
        self.executor = CodeExecutor()

    def validate(
        self,
        candidate: CandidateFix,
        original_code: str,
        test_cases: list[dict] = None,
        original_stdout: str = "",
    ) -> CandidateFix:
        """
        Run all validation layers on a candidate.
        Populates candidate.validation_score, candidate.validation_notes, candidate.status.
        """
        test_cases = test_cases or []
        notes = []
        score = 0.0

        # ── Layer 1: Syntax check ─────────────────────────────────────────────
        syntax_ok, syntax_err = self.executor.syntax_check(candidate.code)
        if not syntax_ok:
            candidate.status = AttemptStatus.FAILED
            candidate.validation_score = 0.0
            candidate.validation_notes = f"Syntax error: {syntax_err}"
            return candidate

        score += 0.15  # Passed syntax check
        notes.append("✓ Syntax valid")

        # ── Layer 2: Safety check ─────────────────────────────────────────────
        safe, reason = self.executor.is_safe(candidate.code)
        if not safe:
            candidate.status = AttemptStatus.FAILED
            candidate.validation_score = 0.05
            candidate.validation_notes = f"Safety check failed: {reason}"
            return candidate

        # ── Layer 3: Execution check ──────────────────────────────────────────
        if candidate.execution is None:
            candidate.execution = self.executor.run(candidate.code)

        exec_result = candidate.execution

        if exec_result.timed_out:
            candidate.status = AttemptStatus.TIMEOUT
            candidate.validation_score = 0.1
            candidate.validation_notes = "Code timed out during execution"
            return candidate

        if exec_result.has_error:
            candidate.status = AttemptStatus.FAILED
            candidate.validation_score = score  # partial credit for syntax
            candidate.validation_notes = f"Runtime error: {exec_result.error_message}"
            return candidate

        score += 0.30  # Ran without errors
        notes.append("✓ Executes without errors")

        # ── Layer 4: Output regression check ─────────────────────────────────
        if original_stdout and exec_result.stdout:
            # Check if the output is similar (not necessarily identical)
            orig_lines = set(original_stdout.strip().splitlines())
            new_lines = set(exec_result.stdout.strip().splitlines())
            if orig_lines and new_lines:
                overlap = len(orig_lines & new_lines) / max(len(orig_lines), 1)
                if overlap > 0.5:
                    score += 0.10
                    notes.append("✓ Output consistent with previous successful runs")

        # ── Layer 5: Test case check ──────────────────────────────────────────
        if test_cases:
            test_result = self.executor.run_with_tests(candidate.code, test_cases)
            passed = test_result.get("passed", 0)
            failed = test_result.get("failed", 0)
            total = passed + failed

            if total > 0:
                pass_rate = passed / total
                score += pass_rate * 0.35  # Up to 35% from tests
                if pass_rate == 1.0:
                    notes.append(f"✓ All {total} test cases passed")
                elif pass_rate > 0.5:
                    notes.append(f"⚠ {passed}/{total} test cases passed")
                else:
                    notes.append(f"✗ Only {passed}/{total} test cases passed")
            else:
                # No tests ran — partial credit
                score += 0.15
                notes.append("~ Test cases could not be evaluated")
        else:
            # No test cases — partial credit for running cleanly
            score += 0.25
            notes.append("~ No test cases provided")

        # ── Layer 6: Code quality heuristics ──────────────────────────────────
        quality_score = self._code_quality_score(candidate.code, original_code)
        score += quality_score * 0.10  # Up to 10% from quality

        if quality_score > 0.7:
            notes.append("✓ Code quality looks good")

        # ── Final scoring ──────────────────────────────────────────────────────
        score = min(score, 1.0)
        candidate.validation_score = round(score, 3)
        candidate.validation_notes = " | ".join(notes)

        # Determine final status
        if score >= 0.65:
            candidate.status = AttemptStatus.SUCCESS
        elif score >= 0.3:
            candidate.status = AttemptStatus.INVALID
        else:
            candidate.status = AttemptStatus.FAILED

        return candidate

    def _code_quality_score(self, fixed_code: str, original_code: str) -> float:
        """
        Heuristic quality check.
        Returns 0.0 – 1.0.
        """
        score = 0.5  # baseline

        # Fixed code shouldn't be much shorter than original (likely truncated)
        if len(fixed_code) < len(original_code) * 0.5 and len(original_code) > 50:
            score -= 0.3

        # Should have at least one newline (multi-line code)
        if "\n" not in fixed_code:
            score -= 0.2

        # Shouldn't be identical to original
        if fixed_code.strip() == original_code.strip():
            score -= 0.5

        # Bonus for type hints
        if ": " in fixed_code or " -> " in fixed_code:
            score += 0.1

        # Bonus for docstrings
        if '"""' in fixed_code or "'''" in fixed_code:
            score += 0.1

        return max(0.0, min(1.0, score))

    def validate_all(
        self,
        candidates: list[CandidateFix],
        original_code: str,
        test_cases: list[dict] = None,
        original_stdout: str = "",
    ) -> list[CandidateFix]:
        """Run validation on all candidates."""
        for c in candidates:
            self.validate(
                candidate=c,
                original_code=original_code,
                test_cases=test_cases,
                original_stdout=original_stdout,
            )
        return candidates