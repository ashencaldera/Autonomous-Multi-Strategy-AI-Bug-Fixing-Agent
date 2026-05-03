"""
Agent Controller
The central brain of the autonomous bug-fixing agent.
Orchestrates all tools in a loop with full autonomy:
Execute → Capture → Search → Reflect → Plan → Test → Validate → Select → Stop
"""

import time
import uuid
import logging
from typing import Generator

from .memory import AgentMemory, AttemptStatus, CandidateFix
from .executor import CodeExecutor
from .error_searcher import ErrorSearcher
from .reflector import Reflector
from .planner import Planner
from .validator import Validator

logger = logging.getLogger(__name__)

# Agent limits
MAX_ATTEMPTS = 3
MAX_CANDIDATES_PER_ROUND = 4
MIN_VALIDATION_SCORE = 0.55   # Candidate must score above this to be "selected"
TARGET_VALIDATION_SCORE = 0.80  # Agent stops immediately if a candidate hits this


class AgentController:
    """
    Autonomous multi-strategy Python bug-fixing agent.

    Runs a self-correcting loop:
    1. Execute original code → capture error
    2. Search / analyse the error
    3. Reflect on prior failures
    4. Generate N candidate fixes with different strategies
    5. Execute + validate each candidate
    6. Select the best; if good enough → done
    7. Otherwise loop (up to MAX_ATTEMPTS)
    """

    def __init__(self):
        self.executor = CodeExecutor()
        self.searcher = ErrorSearcher()
        self.reflector = Reflector()
        self.planner = Planner()
        self.validator = Validator()

    # ── Public entry point ────────────────────────────────────────────────────

    def fix(self, code: str) -> AgentMemory:
        """
        Synchronous fix. Returns the completed AgentMemory when done.
        Use fix_stream() for real-time UI updates.
        """
        memory = AgentMemory(session_id=str(uuid.uuid4()), original_code=code)
        start = time.time()

        for _ in self._run_loop(memory, code):
            pass  # consume the generator

        memory.total_duration_ms = (time.time() - start) * 1000
        return memory

    def fix_stream(self, code: str) -> Generator[dict, None, None]:
        """
        Streaming fix — yields event dicts at each step.
        Frontend can consume this via SSE for real-time updates.

        Event format:
        {
          "event": "step" | "result" | "error" | "done",
          "data": { ... }
        }
        """
        memory = AgentMemory(session_id=str(uuid.uuid4()), original_code=code)
        start = time.time()

        try:
            yield from self._run_loop(memory, code)
        except Exception as e:
            logger.exception("Agent loop crashed")
            yield {
                "event": "error",
                "data": {"message": str(e), "session_id": memory.session_id},
            }

        memory.total_duration_ms = (time.time() - start) * 1000
        yield {
            "event": "done",
            "data": memory.to_summary(),
        }

    # ── Core loop ─────────────────────────────────────────────────────────────

    def _run_loop(self, memory: AgentMemory, code: str) -> Generator[dict, None, None]:
        """Internal loop generator — yields event dicts."""

        # ── STEP 0: Check syntax first (fast path) ────────────────────────────
        step = memory.add_step("Syntax Pre-check", "Checking code syntax before execution")
        syntax_ok, syntax_err = self.executor.syntax_check(code)

        if syntax_ok:
            memory.update_step(step, "done", "Syntax looks valid — proceeding to execution")
            yield self._step_event(step)
        else:
            memory.update_step(step, "done", f"Syntax error detected: {syntax_err}")
            yield self._step_event(step)

        # ── STEP 1: Execute original code ─────────────────────────────────────
        step = memory.add_step("Execute Original Code", "Running your code to capture the error")
        yield self._step_event(step)

        original_exec = self.executor.run(code)
        original_stdout = original_exec.stdout  # Save for regression testing

        if not original_exec.has_error:
            # Code already works!
            memory.update_step(step, "done", "Code ran successfully with no errors")
            yield self._step_event(step)
            memory.final_code = code
            memory.final_status = "success"
            yield {
                "event": "result",
                "data": {
                    "status": "already_working",
                    "message": "Your code has no errors!",
                    "original_output": original_exec.stdout,
                    "fixed_code": code,
                },
            }
            return

        memory.update_step(
            step, "done",
            f"Error captured: {original_exec.error_type} — {original_exec.error_message[:120]}"
        )
        yield self._step_event(step)
        yield {
            "event": "execution_result",
            "data": {
                "error_type": original_exec.error_type,
                "error_message": original_exec.error_message,
                "traceback": original_exec.traceback,
                "stdout": original_exec.stdout,
            },
        }

        # ── STEP 2: Analyse the error ─────────────────────────────────────────
        step = memory.add_step("Analyse Error", "Using AI to understand the root cause")
        yield self._step_event(step)

        error_analysis = self.searcher.analyze(code, original_exec)

        memory.update_step(
            step, "done",
            f"Category: {error_analysis.get('error_category')} | "
            f"{error_analysis.get('plain_english', '')[:120]}"
        )
        yield self._step_event(step)
        yield {
            "event": "error_analysis",
            "data": error_analysis,
        }

        # Generate test cases once
        test_cases = error_analysis.get("test_cases", [])
        if not test_cases:
            test_cases = self.planner.generate_test_cases_for_code(code, error_analysis)

        # ── Main fixing loop ───────────────────────────────────────────────────
        best_candidate: CandidateFix | None = None

        for attempt_num in range(1, MAX_ATTEMPTS + 1):
            attempt = memory.new_attempt(error=original_exec.full_error)

            # STEP 3: Reflect ─────────────────────────────────────────────────
            step = memory.add_step(
                f"Reflect (Attempt {attempt_num})",
                "Learning from previous failures" if attempt_num > 1 else "Preparing strategy for first attempt"
            )
            yield self._step_event(step)

            reflection = self.reflector.reflect(
                original_code=code,
                error_analysis=error_analysis,
                failed_fixes=memory.get_failed_fixes(),
                attempt_number=attempt_num,
            )
            attempt.reflection = reflection.get("summary", "")

            memory.update_step(step, "done", reflection.get("new_approach", "")[:120])
            yield self._step_event(step)
            yield {
                "event": "reflection",
                "data": {
                    "attempt": attempt_num,
                    "reflection": reflection,
                },
            }

            # STEP 4: Generate candidates ─────────────────────────────────────
            step = memory.add_step(
                f"Generate Fixes (Attempt {attempt_num})",
                f"Creating {MAX_CANDIDATES_PER_ROUND} candidate fixes using different strategies"
            )
            yield self._step_event(step)

            # Adapt strategies based on attempt number
            strategies = self._pick_strategies(attempt_num, reflection)

            candidates = self.planner.generate_fixes(
                original_code=code,
                error_analysis=error_analysis,
                reflection=reflection,
                strategies=strategies,
                num_candidates=MAX_CANDIDATES_PER_ROUND,
            )

            # Filter already-tried code
            fresh = [c for c in candidates if not memory.has_tried_code(c.code)]
            if not fresh:
                fresh = candidates  # Use them anyway if all are duplicates

            attempt.candidates = fresh
            memory.update_step(step, "done", f"Generated {len(fresh)} unique candidates")
            yield self._step_event(step)
            yield {
                "event": "candidates_generated",
                "data": {
                    "attempt": attempt_num,
                    "count": len(fresh),
                    "strategies": [c.strategy for c in fresh],
                },
            }

            # STEP 5: Execute + Validate each candidate ───────────────────────
            step = memory.add_step(
                f"Test Candidates (Attempt {attempt_num})",
                f"Executing and validating {len(fresh)} fixes"
            )
            yield self._step_event(step)

            validated: list[CandidateFix] = []
            for i, candidate in enumerate(fresh):
                # Execute
                candidate.execution = self.executor.run(candidate.code)

                # Validate
                self.validator.validate(
                    candidate=candidate,
                    original_code=code,
                    test_cases=test_cases,
                    original_stdout=original_stdout,
                )

                validated.append(candidate)

                yield {
                    "event": "candidate_result",
                    "data": {
                        "attempt": attempt_num,
                        "index": i,
                        "candidate_id": candidate.id,
                        "strategy": candidate.strategy,
                        "status": candidate.status,
                        "validation_score": candidate.validation_score,
                        "validation_notes": candidate.validation_notes,
                        "explanation": candidate.explanation,
                        "code": candidate.code,
                        "stdout": candidate.execution.stdout if candidate.execution else "",
                        "stderr": candidate.execution.stderr if candidate.execution else "",
                    },
                }

            # STEP 6: Select the best candidate ───────────────────────────────
            best = self._select_best(validated)
            attempt.selected = best

            memory.update_step(
                step, "done",
                f"Best: {best.strategy if best else 'none'} | "
                f"Score: {best.validation_score:.2f}" if best else "No valid candidate found"
            )
            yield self._step_event(step)

            if best and best.validation_score >= MIN_VALIDATION_SCORE:
                best_candidate = best
                yield {
                    "event": "best_selected",
                    "data": {
                        "attempt": attempt_num,
                        "candidate_id": best.id,
                        "strategy": best.strategy,
                        "score": best.validation_score,
                        "notes": best.validation_notes,
                    },
                }

                # If score is high enough, stop immediately
                if best.validation_score >= TARGET_VALIDATION_SCORE:
                    break

            # If all candidates failed badly, continue to next attempt
            if not best_candidate:
                yield {
                    "event": "attempt_failed",
                    "data": {
                        "attempt": attempt_num,
                        "message": "No candidate met the minimum quality threshold — retrying",
                    },
                }

        # ── Final result ───────────────────────────────────────────────────────
        if best_candidate:
            memory.final_code = best_candidate.code
            memory.final_status = "success"
            yield {
                "event": "result",
                "data": {
                    "status": "fixed",
                    "fixed_code": best_candidate.code,
                    "strategy": best_candidate.strategy,
                    "explanation": best_candidate.explanation,
                    "diff_summary": best_candidate.diff_summary,
                    "validation_score": best_candidate.validation_score,
                    "validation_notes": best_candidate.validation_notes,
                    "output": best_candidate.execution.stdout if best_candidate.execution else "",
                    "attempts_made": len(memory.attempts),
                },
            }
        else:
            memory.final_status = "failed"
            # Find the best we've got even if below threshold
            all_candidates = [
                c for a in memory.attempts for c in a.candidates
            ]
            best_effort = self._select_best(all_candidates)
            yield {
                "event": "result",
                "data": {
                    "status": "failed",
                    "message": f"Could not find a fully verified fix after {MAX_ATTEMPTS} attempts.",
                    "best_effort_code": best_effort.code if best_effort else code,
                    "best_effort_score": best_effort.validation_score if best_effort else 0,
                    "best_effort_explanation": best_effort.explanation if best_effort else "",
                    "attempts_made": len(memory.attempts),
                },
            }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _select_best(self, candidates: list[CandidateFix]) -> CandidateFix | None:
        """Select the candidate with the highest validation score."""
        if not candidates:
            return None
        scored = [c for c in candidates if c.validation_score > 0]
        if not scored:
            return candidates[0]
        return max(scored, key=lambda c: (c.validation_score, c.confidence))

    def _pick_strategies(self, attempt_num: int, reflection: dict) -> list[str]:
        """Choose fix strategies based on attempt number and reflection."""
        if attempt_num == 1:
            return ["minimal", "defensive", "refactored", "typed"]
        elif attempt_num == 2:
            # On retry, lead with refactored (fresh approach)
            return ["refactored", "typed", "defensive", "minimal"]
        else:
            # Final attempt — try all again, reflection has updated guidance
            return ["defensive", "refactored", "minimal", "typed"]

    @staticmethod
    def _step_event(step) -> dict:
        return {
            "event": "step",
            "data": {
                "name": step.name,
                "status": step.status,
                "detail": step.detail,
            },
        }