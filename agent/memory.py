"""
Agent Memory System
Stores all attempts, errors, fixes, reflections, and results
per session. Prevents repeated mistakes and supports learning.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class AttemptStatus(str, Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    FAILED     = "failed"
    SUCCESS    = "success"
    INVALID    = "invalid"   # Ran but validation failed
    TIMEOUT    = "timeout"


@dataclass
class ExecutionResult:
    stdout: str = ""
    stderr: str = ""
    error_type: str = ""
    error_message: str = ""
    traceback: str = ""
    exit_code: int = 0
    timed_out: bool = False
    duration_ms: float = 0.0

    @property
    def has_error(self) -> bool:
        return bool(self.stderr or self.error_message or self.timed_out)

    @property
    def full_error(self) -> str:
        return self.traceback or self.stderr or self.error_message


@dataclass
class CandidateFix:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    strategy: str = ""          # "minimal", "defensive", "refactored", "typed"
    code: str = ""
    explanation: str = ""
    confidence: float = 0.0     # 0.0 – 1.0
    diff_summary: str = ""

    # After testing:
    execution: Optional[ExecutionResult] = None
    validation_score: float = 0.0
    validation_notes: str = ""
    status: AttemptStatus = AttemptStatus.PENDING


@dataclass
class AgentAttempt:
    attempt_number: int = 0
    timestamp: float = field(default_factory=time.time)

    original_error: str = ""
    error_explanation: str = ""
    reflection: str = ""

    candidates: list[CandidateFix] = field(default_factory=list)
    selected: Optional[CandidateFix] = None

    duration_ms: float = 0.0


@dataclass
class AgentStep:
    """A single observable step in the agent's reasoning process."""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    status: str = "running"   # running | done | error
    detail: str = ""
    timestamp: float = field(default_factory=time.time)


class AgentMemory:
    """
    Full session memory for the bug-fixing agent.
    Tracks every attempt, step, and decision made during a session.
    """

    def __init__(self, session_id: str, original_code: str):
        self.session_id = session_id
        self.original_code = original_code
        self.created_at = time.time()

        self.attempts: list[AgentAttempt] = []
        self.steps: list[AgentStep] = []

        self.final_code: Optional[str] = None
        self.final_status: str = "in_progress"  # success | failed | in_progress
        self.total_duration_ms: float = 0.0

        # Track all errors seen (to avoid repeating fixes)
        self.seen_errors: set[str] = set()
        # Track all code tried (to avoid exact duplicates)
        self.tried_code_hashes: set[int] = set()

    # ── Step logging ──────────────────────────────────────────────────────────

    def add_step(self, name: str, detail: str = "", status: str = "running") -> AgentStep:
        step = AgentStep(name=name, detail=detail, status=status)
        self.steps.append(step)
        return step

    def update_step(self, step: AgentStep, status: str, detail: str = ""):
        step.status = status
        if detail:
            step.detail = detail

    # ── Attempt management ────────────────────────────────────────────────────

    def new_attempt(self, error: str = "") -> AgentAttempt:
        attempt = AgentAttempt(
            attempt_number=len(self.attempts) + 1,
            original_error=error,
        )
        self.attempts.append(attempt)
        if error:
            self.seen_errors.add(error[:200])  # store prefix for dedup
        return attempt

    @property
    def current_attempt(self) -> Optional[AgentAttempt]:
        return self.attempts[-1] if self.attempts else None

    @property
    def all_tried_codes(self) -> list[str]:
        codes = [self.original_code]
        for attempt in self.attempts:
            for c in attempt.candidates:
                codes.append(c.code)
        return codes

    def has_tried_code(self, code: str) -> bool:
        h = hash(code.strip())
        if h in self.tried_code_hashes:
            return True
        self.tried_code_hashes.add(h)
        return False

    def get_error_history(self) -> list[str]:
        return [a.original_error for a in self.attempts if a.original_error]

    def get_failed_fixes(self) -> list[dict]:
        """Return all failed candidates for reflection context."""
        failed = []
        for attempt in self.attempts:
            for c in attempt.candidates:
                if c.status in (AttemptStatus.FAILED, AttemptStatus.INVALID):
                    failed.append({
                        "strategy": c.strategy,
                        "code": c.code,
                        "explanation": c.explanation,
                        "error": c.execution.full_error if c.execution else "unknown",
                        "validation_notes": c.validation_notes,
                    })
        return failed

    def to_summary(self) -> dict:
        """Serializable summary for the frontend."""
        return {
            "session_id": self.session_id,
            "final_status": self.final_status,
            "attempts_made": len(self.attempts),
            "total_candidates_tested": sum(len(a.candidates) for a in self.attempts),
            "steps": [
                {
                    "name": s.name,
                    "status": s.status,
                    "detail": s.detail,
                }
                for s in self.steps
            ],
            "attempts": [
                {
                    "number": a.attempt_number,
                    "error": a.original_error[:300] if a.original_error else "",
                    "explanation": a.error_explanation[:500] if a.error_explanation else "",
                    "reflection": a.reflection[:500] if a.reflection else "",
                    "candidates": [
                        {
                            "id": c.id,
                            "strategy": c.strategy,
                            "status": c.status,
                            "confidence": c.confidence,
                            "explanation": c.explanation,
                            "validation_score": c.validation_score,
                            "diff_summary": c.diff_summary,
                        }
                        for c in a.candidates
                    ],
                    "selected": a.selected.id if a.selected else None,
                }
                for a in self.attempts
            ],
            "final_code": self.final_code,
            "total_duration_ms": self.total_duration_ms,
        }