from typing import Any

from app.config import Settings


class ChatModelFactory:
    """Create the configured chat model without coupling the Agent to a vendor."""

    @staticmethod
    def create(settings: Settings, tools: list[dict[str, Any]]) -> Any | None:
        if not settings.llm_enabled or not settings.llm_api_key:
            return None

        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            timeout=settings.llm_timeout_seconds,
            max_retries=1,
            extra_body={"enable_thinking": False},
        )
        return model.bind_tools(tools)
