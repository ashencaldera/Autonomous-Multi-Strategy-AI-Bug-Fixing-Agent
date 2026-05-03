"""
Reflector Module
Metacognitive component that analyzes WHY previous fixes failed.
This is what makes the agent self-correcting — it learns from mistakes
within a session and avoids repeating the same errors.
"""

import logging
from llm.groq_client import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior Python engineer doing a code review of failed AI-generated bug fixes.
Your job is to understand WHY previous fixes didn't work and guide the next attempt.
Be specific, technical, and concise. Respond with valid JSON only."""


class Reflector:
    """
    Analyzes failed fix attempts and produces reflection insights
    to improve the next round of fix generation.
    """

    def __init__(self):
        self.llm = get_llm()

    def reflect(
        self,
        original_code: str,
        error_analysis: dict,
        failed_fixes: list[dict],
        attempt_number: int,
    ) -> dict:
        """
        Produce a structured reflection on why previous fixes failed.

        Returns:
        {
          "summary": "...",
          "root_mistakes": ["..."],
          "what_to_avoid": ["..."],
          "new_approach": "...",
          "confidence_boost_tips": ["..."]
        }
        """
        if not failed_fixes:
            return self._no_history_reflection(error_analysis)

        failed_summary = "\n\n".join([
            f"--- Fix #{i+1} (Strategy: {f.get('strategy', 'unknown')}) ---\n"
            f"Explanation: {f.get('explanation', '')}\n"
            f"Code snippet:\n```python\n{f.get('code', '')[:800]}\n```\n"
            f"Result: {f.get('error', 'unknown error')}\n"
            f"Validation notes: {f.get('validation_notes', '')}"
            for i, f in enumerate(failed_fixes[-4:])  # last 4 only
        ])

        prompt = f"""We are on attempt #{attempt_number} of fixing buggy Python code.
Previous fixes have FAILED. Analyze why and guide the next attempt.

## Original Buggy Code:
```python
{original_code[:1000]}
```

## Error Analysis:
- Plain English: {error_analysis.get('plain_english', '')}
- Root Cause: {error_analysis.get('root_cause', '')}
- Category: {error_analysis.get('error_category', '')}
- Fix Hints: {error_analysis.get('fix_hints', [])}

## Failed Fix Attempts:
{failed_summary}

Analyze what went wrong in each attempt and return a JSON object:
{{
  "summary": "One paragraph summary of what's been tried and why it's failing",
  "root_mistakes": ["Mistake 1 made in previous fixes", "Mistake 2", ...],
  "what_to_avoid": ["Do NOT do X", "Do NOT do Y", ...],
  "new_approach": "Concrete description of a fundamentally different approach to try next",
  "key_insight": "The most important insight that previous fixes missed",
  "confidence_boost_tips": ["Specific tip for writing a correct fix", ...]
}}"""

        try:
            result = self.llm.chat_json(
                messages=[{"role": "user", "content": prompt}],
                system=SYSTEM_PROMPT,
                model="default",
                temperature=0.2,
            )
            result.setdefault("summary", "Previous fixes failed to resolve the issue.")
            result.setdefault("root_mistakes", [])
            result.setdefault("what_to_avoid", [])
            result.setdefault("new_approach", "Try a completely different approach.")
            result.setdefault("key_insight", "")
            result.setdefault("confidence_boost_tips", [])
            return result

        except Exception as e:
            logger.error(f"Reflector failed: {e}")
            return self._fallback_reflection(error_analysis)

    def _no_history_reflection(self, error_analysis: dict) -> dict:
        """First attempt — no prior failures to reflect on."""
        return {
            "summary": "First attempt. No prior failures to reflect on.",
            "root_mistakes": [],
            "what_to_avoid": ["Introducing new bugs while fixing the existing one"],
            "new_approach": f"Focus on: {error_analysis.get('root_cause', 'the reported error')}",
            "key_insight": error_analysis.get("plain_english", ""),
            "confidence_boost_tips": error_analysis.get("fix_hints", []),
        }

    def _fallback_reflection(self, error_analysis: dict) -> dict:
        return {
            "summary": "Reflection failed — proceeding with fresh approach.",
            "root_mistakes": ["Unknown — reflection step errored"],
            "what_to_avoid": ["Repeating the exact same code structure"],
            "new_approach": "Generate completely different fix strategies",
            "key_insight": "",
            "confidence_boost_tips": [],
        }

    def to_text(self, reflection: dict) -> str:
        """Human-readable version of the reflection."""
        lines = [f"📝 {reflection.get('summary', '')}"]
        if reflection.get("key_insight"):
            lines.append(f"💡 Key Insight: {reflection['key_insight']}")
        if reflection.get("new_approach"):
            lines.append(f"🔄 New Approach: {reflection['new_approach']}")
        if reflection.get("what_to_avoid"):
            lines.append("⛔ Avoid:")
            for x in reflection["what_to_avoid"]:
                lines.append(f"   • {x}")
        return "\n".join(lines)