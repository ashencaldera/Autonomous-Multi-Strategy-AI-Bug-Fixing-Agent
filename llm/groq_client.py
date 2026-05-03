"""
Groq LLM Client - Centralized interface for all LLM calls.
Supports streaming, retries, token tracking, and structured outputs.
"""

import os
import json
import time
import logging
from typing import Optional, Generator
from groq import Groq

logger = logging.getLogger(__name__)


class GroqClient:
    """
    Production-grade Groq API wrapper with retry logic,
    token tracking, and structured output support.
    """

    # Available models (in order of capability)
    MODELS = {
        "fast":    "llama-3.1-8b-instant",
        "default": "llama-3.3-70b-versatile",
        "smart":   "llama-3.3-70b-versatile",
    }

    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set.")
        self.client = Groq(api_key=api_key)
        self.total_tokens_used = 0
        self.total_calls = 0

    def chat(
        self,
        messages: list[dict],
        system: str = "",
        model: str = "default",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        retries: int = 3,
        json_mode: bool = False,
    ) -> str:
        """
        Send a chat completion request with retry logic.
        Returns the assistant's text response.
        """
        model_id = self.MODELS.get(model, self.MODELS["default"])

        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        kwargs = {
            "model": model_id,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_error = None
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content

                # Token tracking
                if hasattr(response, "usage") and response.usage:
                    self.total_tokens_used += response.usage.total_tokens
                self.total_calls += 1

                return content.strip()

            except Exception as e:
                last_error = e
                logger.warning(f"Groq API attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        raise RuntimeError(f"Groq API failed after {retries} attempts: {last_error}")

    def chat_json(
        self,
        messages: list[dict],
        system: str = "",
        model: str = "default",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Chat completion that returns parsed JSON.
        Adds JSON instruction to system prompt automatically.
        """
        json_system = system
        if "json" not in system.lower():
            json_system = system + "\n\nYou MUST respond with valid JSON only. No markdown, no explanation outside JSON."

        raw = self.chat(
            messages=messages,
            system=json_system,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}\nRaw: {raw[:500]}")
            raise ValueError(f"LLM did not return valid JSON: {e}")

    def get_stats(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens_used,
        }


# Singleton instance
_client: Optional[GroqClient] = None


def get_llm() -> GroqClient:
    global _client
    if _client is None:
        _client = GroqClient()
    return _client