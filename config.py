"""
Configuration
All settings in one place. Reads from environment variables with safe defaults.
"""

import os
from dataclasses import dataclass


@dataclass
class Config:
    # Flask
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("PORT", 5000))

    # Groq
    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")

    # Agent
    MAX_ATTEMPTS: int = int(os.environ.get("MAX_ATTEMPTS", 3))
    MAX_CANDIDATES: int = int(os.environ.get("MAX_CANDIDATES", 4))
    EXECUTION_TIMEOUT: int = int(os.environ.get("EXECUTION_TIMEOUT", 10))
    MAX_CODE_LENGTH: int = int(os.environ.get("MAX_CODE_LENGTH", 5000))
    MIN_VALIDATION_SCORE: float = float(os.environ.get("MIN_VALIDATION_SCORE", 0.55))

    # Logging
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")


config = Config()