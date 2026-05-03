"""
Error Searcher Tool
Uses LLM to deeply analyze Python errors:
- Explains what the error means in plain English
- Identifies the root cause in the specific code
- Lists likely contributing factors
- Suggests what to look for when fixing
- Generates targeted test cases
"""

import logging
from llm.groq_client import get_llm
from .memory import ExecutionResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Python debugger with 20 years of experience.
Your job is to deeply analyze Python errors and provide structured diagnostic insight.
You must respond with valid JSON only."""


class ErrorSearcher:
    """
    Analyzes Python errors and tracebacks using LLM reasoning.
    Provides rich context to help the fixer generate better solutions.
    """

    def __init__(self):
        self.llm = get_llm()

    def analyze(self, code: str, execution: ExecutionResult) -> dict:
        """
        Perform deep error analysis.
        Returns structured diagnostic information.
        """
        prompt = f"""Analyze this Python error and return a JSON object.

## Code That Failed:
```python
{code}
```

## Error Output:
```
{execution.full_error or execution.stderr or "No error output captured"}
```

## Error Type: {execution.error_type}
## Error Message: {execution.error_message}

Return a JSON object with exactly these fields:
{{
  "plain_english": "Simple 1-2 sentence explanation of what went wrong",
  "root_cause": "The specific line or pattern in the code that caused this error",
  "error_category": one of ["syntax", "runtime", "logic", "type", "name", "import", "index", "attribute", "value", "recursion", "memory", "other"],
  "severity": one of ["minor", "moderate", "major"],
  "contributing_factors": ["factor1", "factor2"],
  "fix_hints": ["hint1", "hint2", "hint3"],
  "common_mistake": "Is this a common beginner mistake? Brief description.",
  "test_cases": [
    {{"call": "function_name(args)", "expected": "expected_output_as_string"}}
  ],
  "confidence": 0.0-1.0
}}

If you cannot determine test cases from the code, use an empty list.
For test cases, only include ones where you can determine the function/call signature from the code."""

        try:
            result = self.llm.chat_json(
                messages=[{"role": "user", "content": prompt}],
                system=SYSTEM_PROMPT,
                model="default",
                temperature=0.1,
            )
            # Ensure required fields exist
            result.setdefault("plain_english", "An error occurred in the code.")
            result.setdefault("root_cause", execution.error_message)
            result.setdefault("error_category", "other")
            result.setdefault("severity", "moderate")
            result.setdefault("contributing_factors", [])
            result.setdefault("fix_hints", [])
            result.setdefault("common_mistake", "")
            result.setdefault("test_cases", [])
            result.setdefault("confidence", 0.7)
            return result

        except Exception as e:
            logger.error(f"Error searcher failed: {e}")
            return {
                "plain_english": f"Error: {execution.error_message}",
                "root_cause": execution.full_error,
                "error_category": "other",
                "severity": "moderate",
                "contributing_factors": [],
                "fix_hints": ["Review the traceback carefully"],
                "common_mistake": "",
                "test_cases": [],
                "confidence": 0.5,
            }

    def get_explanation_text(self, analysis: dict) -> str:
        """Convert analysis dict to readable text for logging/display."""
        lines = [
            f"🔍 {analysis.get('plain_english', '')}",
            f"🎯 Root Cause: {analysis.get('root_cause', '')}",
            f"📂 Category: {analysis.get('error_category', '')} | Severity: {analysis.get('severity', '')}",
        ]
        if analysis.get("fix_hints"):
            lines.append("💡 Fix Hints:")
            for hint in analysis["fix_hints"]:
                lines.append(f"   • {hint}")
        return "\n".join(lines)