import os
from datetime import date


class Settings:
    # Seed data (invoice history, contract terms, renewal dates) is generated
    # relative to this fixed reference date rather than the real wall clock,
    # so the demo's "upcoming renewals" / "current effective terms" views
    # stay meaningful no matter when this is actually run.
    demo_today: date = date(2026, 7, 15)

    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
    groq_api_key: str | None = os.getenv("GROQ_API_KEY") or None
    stripe_api_key: str | None = os.getenv("STRIPE_API_KEY") or None

    @property
    def llm_mode(self) -> str:
        if self.gemini_api_key:
            return "gemini"
        if self.groq_api_key:
            return "groq"
        return "demo"

    @property
    def is_demo_mode(self) -> bool:
        return self.llm_mode == "demo"


settings = Settings()
