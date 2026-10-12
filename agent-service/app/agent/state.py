from typing import Any, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    conversation_id: str
    message: str
    token: str | None
    messages: list[BaseMessage]
    constraints: dict[str, Any]
    missing_fields: list[str]
    tickets: list[dict[str, Any]]
    ticket_catalog: list[dict[str, Any]]
    itineraries: list[dict[str, Any]]
    answer: str
    status: str
    trace: list[dict[str, Any]]
