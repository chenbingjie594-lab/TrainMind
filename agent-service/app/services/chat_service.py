import json
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, messages_from_dict, messages_to_dict

from app.agent.react_agent import ReactAgent
from app.models.chat import ChatRequest, ChatResponse
from app.models.ticket import SearchConstraints
from app.services.session_store import SessionStore


class ChatService:
    def __init__(self, graph: ReactAgent, sessions: SessionStore) -> None:
        # Keep the historical argument name for callers; this is now a ReactAgent.
        self._agent = graph
        self._sessions = sessions

    async def chat(self, request: ChatRequest, token: str | None = None) -> ChatResponse:
        conversation_id = request.conversation_id or uuid4().hex
        owner_id = self._owner_id(token)
        previous = await self._sessions.get(owner_id, conversation_id) or {}
        history = messages_from_dict(previous.get("messages", []))
        initial = {
            "conversation_id": conversation_id,
            "message": request.message,
            "token": token,
            "constraints": previous.get("constraints", {}),
            "messages": [*history, HumanMessage(content=request.message)],
            "trace": [],
        }
        result = await self._agent.execute(initial)
        display_messages = list(previous.get("display_messages", []))
        display_messages.extend(
            [
                {
                    "role": "user",
                    "content": request.message,
                    "time": datetime.now(UTC).isoformat(),
                },
                {
                    "role": "assistant",
                    "content": result.get("answer", ""),
                    "time": datetime.now(UTC).isoformat(),
                    "constraints": result.get("constraints", {}),
                    "tickets": [
                        item.model_dump(mode="json", by_alias=True)
                        if hasattr(item, "model_dump")
                        else item
                        for item in result.get("tickets", [])
                    ],
                    "itineraries": [
                        item.model_dump(mode="json", by_alias=True)
                        if hasattr(item, "model_dump")
                        else item
                        for item in result.get("itineraries", [])
                    ],
                },
            ]
        )
        saved = {
            "constraints": result.get("constraints", {}),
            "status": result.get("status"),
            "messages": messages_to_dict(result.get("messages", [])),
            "display_messages": display_messages,
        }
        await self._sessions.put(owner_id, conversation_id, saved)
        return ChatResponse(
            conversationId=conversation_id,
            message=result.get("answer", ""),
            status=result.get("status", "COMPLETED"),
            constraints=SearchConstraints.model_validate(result.get("constraints", {})),
            missingFields=result.get("missing_fields", []),
            tickets=result.get("tickets", []),
            itineraries=result.get("itineraries", []),
            trace=result.get("trace", []),
        )

    async def history(
        self, conversation_id: str, token: str | None = None
    ) -> list[dict[str, Any]] | None:
        previous = await self._sessions.get(
            self._owner_id(token), conversation_id
        )
        if previous is None:
            return None
        display_messages = previous.get("display_messages")
        if display_messages is not None:
            return display_messages

        # Compatibility with conversations created before display history existed.
        history: list[dict[str, Any]] = []
        for message in messages_from_dict(previous.get("messages", [])):
            role = getattr(message, "type", "")
            content = getattr(message, "content", "")
            if role in {"human", "ai"} and isinstance(content, str) and content:
                history.append(
                    {
                        "role": "user" if role == "human" else "assistant",
                        "content": content,
                        "time": None,
                    }
                )
        return history

    async def stream(
        self, request: ChatRequest, token: str | None = None
    ) -> AsyncIterator[str]:
        conversation_id = request.conversation_id or uuid4().hex
        yield self._sse("workflow_started", {"conversationId": conversation_id})
        try:
            response = await self.chat(
                ChatRequest(conversationId=conversation_id, message=request.message),
                token,
            )
            yield self._sse(
                "constraints",
                response.constraints.model_dump(mode="json", by_alias=True),
            )
            for trace in response.trace:
                event = "tool_called" if trace["node"] == "search_tickets" else "node_completed"
                yield self._sse(event, trace)
            if response.tickets:
                yield self._sse(
                    "tool_result",
                    {
                        "tool": "search_tickets",
                        "tickets": [item.model_dump(mode="json", by_alias=True) for item in response.tickets],
                    },
                )
            if response.itineraries:
                yield self._sse(
                    "tool_result",
                    {
                        "tool": "select_itineraries",
                        "itineraries": [
                            item.model_dump(mode="json", by_alias=True)
                            for item in response.itineraries
                        ],
                    },
                )
            yield self._sse("message", {"content": response.message})
            yield self._sse(
                "completed",
                response.model_dump(mode="json", by_alias=True),
            )
        except Exception as exc:
            yield self._sse(
                "error",
                {"conversationId": conversation_id, "message": str(exc)},
            )

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    @staticmethod
    def _owner_id(token: str | None) -> str:
        if not token:
            return "anonymous"
        # Never store the original login token in Redis keys or values.
        return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
