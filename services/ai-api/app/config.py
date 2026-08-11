import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_KNOWLEDGE_BASE_PATH = next(
    (
        parent / "knowledge-base"
        for parent in Path(__file__).resolve().parents
        if (parent / "knowledge-base").exists()
    ),
    Path.cwd() / "knowledge-base",
)
DEFAULT_PROMPT_PATH = next(
    (
        parent / "prompts"
        for parent in Path(__file__).resolve().parents
        if (parent / "prompts" / "manifest.json").exists()
    ),
    Path.cwd() / "prompts",
)


@dataclass(frozen=True)
class Settings:
    core_api_base_url: str = "http://localhost:8001"
    ai_mode: str = "auto"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_planner_model: str | None = None
    openai_composer_model: str | None = None
    session_ttl_seconds: int = 30 * 60
    session_max_turns: int = 10
    knowledge_base_path: str = str(DEFAULT_KNOWLEDGE_BASE_PATH)
    business_timezone: str = "Asia/Shanghai"
    prompt_path: str = str(DEFAULT_PROMPT_PATH)
    state_database_path: str = "./data/ai-state.db"

    @classmethod
    def from_env(cls) -> "Settings":
        mode = os.getenv("AI_MODE", "auto").lower()
        if mode not in {"local", "auto", "openai"}:
            raise ValueError("AI_MODE must be local, auto, or openai")
        return cls(
            core_api_base_url=os.getenv(
                "DEMO_CORE_API_BASE_URL", "http://localhost:8001"
            ).rstrip("/"),
            ai_mode=mode,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-terra"),
            openai_planner_model=os.getenv("OPENAI_PLANNER_MODEL") or None,
            openai_composer_model=os.getenv("OPENAI_COMPOSER_MODEL") or None,
            session_ttl_seconds=int(
                os.getenv("SESSION_TTL_SECONDS", str(30 * 60))
            ),
            session_max_turns=int(os.getenv("SESSION_MAX_TURNS", "10")),
            knowledge_base_path=os.getenv(
                "KNOWLEDGE_BASE_PATH", str(DEFAULT_KNOWLEDGE_BASE_PATH)
            ),
            business_timezone=os.getenv("BUSINESS_TIMEZONE", "Asia/Shanghai"),
            prompt_path=os.getenv("PROMPT_PATH", str(DEFAULT_PROMPT_PATH)),
            state_database_path=os.getenv(
                "AI_STATE_DATABASE_PATH", "./data/ai-state.db"
            ),
        )

    @property
    def resolved_mode(self) -> str:
        if self.ai_mode == "auto":
            return "openai" if self.openai_api_key else "local"
        return self.ai_mode
