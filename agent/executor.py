"""
Code Executor Tool
Safely executes Python code in a subprocess with:
- Configurable timeout
- Full stdout/stderr capture
- Structured error parsing
- Traceback extraction
- Resource-limited execution
"""

import ast
import re
import subprocess
import sys
import tempfile
import time
import os
import textwrap
import logging
from .memory import ExecutionResult

logger = logging.getLogger(__name__)

# Dangerous imports/calls that we block
BLOCKED_PATTERNS = [
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\bshutil\.rmtree\b",
    r"\bopen\s*\(.+['\"]w['\"]",   # file write
    r"__import__\s*\(\s*['\"]os['\"]",
    r"\beval\s*\(",
    r"\bexec\s*\(",
]


class CodeExecutor:
    """
    Runs Python code safely in an isolated subprocess.
    Captures all output and parses errors into structured form.
    """

    DEFAULT_TIMEOUT = 10  # seconds
    MAX_OUTPUT_CHARS = 8000

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout

    def is_safe(self, code: str) -> tuple[bool, str]:
        """
        Basic static safety check before execution.
        Returns (is_safe, reason).
        """
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, code):
                return False, f"Blocked pattern detected: {pattern}"
        return True, ""

    def syntax_check(self, code: str) -> tuple[bool, str]:
        """
        Check if code has valid Python syntax without running it.
        Returns (is_valid, error_message).
        """
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, str(e)

    def run(self, code: str) -> ExecutionResult:
        """
        Execute the given Python code string.
        Returns a structured ExecutionResult.
        """
        result = ExecutionResult()
        start = time.time()

        # Safety check
        safe, reason = self.is_safe(code)
        if not safe:
            result.error_message = f"Safety check failed: {reason}"
            result.stderr = result.error_message
            result.exit_code = -1
            return result

        # Write code to temp file
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                encoding="utf-8",
            ) as f:
                f.write(code)
                temp_path = f.name

            # Run in subprocess with timeout
            proc = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=tempfile.gettempdir(),
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )

            result.stdout = proc.stdout[: self.MAX_OUTPUT_CHARS]
            result.stderr = proc.stderr[: self.MAX_OUTPUT_CHARS]
            result.exit_code = proc.returncode

            if proc.stderr:
                parsed = self._parse_error(proc.stderr)
                result.error_type = parsed["error_type"]
                result.error_message = parsed["error_message"]
                result.traceback = parsed["traceback"]

        except subprocess.TimeoutExpired:
            result.timed_out = True
            result.error_type = "TimeoutError"
            result.error_message = f"Code execution timed out after {self.timeout}s"
            result.stderr = result.error_message
            result.exit_code = -1

        except Exception as e:
            result.error_message = str(e)
            result.stderr = str(e)
            result.exit_code = -1
            logger.exception("Executor unexpected error")

        finally:
            result.duration_ms = (time.time() - start) * 1000
            try:
                os.unlink(temp_path)
            except Exception:
                pass

        return result

    def _parse_error(self, stderr: str) -> dict:
        """
        Parse Python traceback into structured components.
        """
        lines = stderr.strip().splitlines()

        error_type = ""
        error_message = ""
        traceback_lines = []

        # Find the last error line (ErrorType: message)
        for line in reversed(lines):
            match = re.match(r"^([A-Za-z][A-Za-z0-9_]*(?:Error|Exception|Warning|Interrupt)?)\s*:\s*(.*)", line)
            if match:
                error_type = match.group(1)
                error_message = match.group(2).strip()
                break

        # Also handle bare SyntaxError with no colon
        if not error_type:
            for line in reversed(lines):
                if re.match(r"^(SyntaxError|IndentationError|TabError)", line):
                    error_type = line.strip()
                    break

        # Full traceback is everything before the final error line
        traceback = "\n".join(lines)

        return {
            "error_type": error_type or "UnknownError",
            "error_message": error_message,
            "traceback": traceback,
        }

    def run_with_tests(self, code: str, test_cases: list[dict]) -> dict:
        """
        Run code and then execute test assertions.
        test_cases: list of {"call": "add(2,3)", "expected": "5"}
        """
        if not test_cases:
            return {"passed": 0, "failed": 0, "results": []}

        test_code_lines = [code, ""]
        test_results = []

        for i, tc in enumerate(test_cases):
            call = tc.get("call", "")
            expected = tc.get("expected", "")
            assertion = f"""
try:
    _result_{i} = {call}
    _expected_{i} = {expected!r}
    if str(_result_{i}) == str(_expected_{i}) or _result_{i} == _expected_{i}:
        print("TEST_{i}:PASS")
    else:
        print(f"TEST_{i}:FAIL:got={{_result_{i}!r}}:expected={{_expected_{i}!r}}")
except Exception as _e_{i}:
    print(f"TEST_{i}:ERROR:{{_e_{i}}}")
"""
            test_code_lines.append(textwrap.dedent(assertion))

        full_code = "\n".join(test_code_lines)
        result = self.run(full_code)

        passed = failed = 0
        for line in result.stdout.splitlines():
            if line.startswith("TEST_") and ":PASS" in line:
                passed += 1
                test_results.append({"status": "pass"})
            elif line.startswith("TEST_") and ":FAIL" in line:
                failed += 1
                test_results.append({"status": "fail", "detail": line})
            elif line.startswith("TEST_") and ":ERROR" in line:
                failed += 1
                test_results.append({"status": "error", "detail": line})

        return {
            "passed": passed,
            "failed": failed,
            "results": test_results,
            "execution": result,
        }