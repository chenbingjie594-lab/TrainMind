from datetime import date
from functools import lru_cache
from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache
def _read_prompt(name: str) -> str:
    path = (PROMPT_DIR / name).resolve()
    if path.parent != PROMPT_DIR.resolve():
        raise ValueError("非法 Prompt 路径")
    return path.read_text(encoding="utf-8").strip()


def load_system_prompt(today: date | None = None) -> str:
    """Load the Agent prompt from disk and inject only runtime-safe values."""

    return _read_prompt("main_prompt.txt").replace(
        "{{today}}", (today or date.today()).isoformat()
    )
