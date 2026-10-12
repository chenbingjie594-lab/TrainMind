import json
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import TextContent

from app.config import Settings
from app.models.ticket import SearchConstraints, TicketOption
from app.tools.business_client import BusinessApiError


class McpTicketClient:
    """Expose MCP ticket tools through the interface expected by the graph."""

    def __init__(self, settings: Settings) -> None:
        self._url = settings.mcp_server_url
        self._timeout = settings.request_timeout_seconds

    async def close(self) -> None:
        return None

    async def search_stations(
        self, keyword: str, token: str | None = None
    ) -> list[dict[str, Any]]:
        result = await self._call("search_stations", {"keyword": keyword}, token)
        data = result.get("data", [])
        return data if isinstance(data, list) else []

    async def list_tickets(
        self,
        travel_date: Any,
        start: str | None = None,
        end: str | None = None,
        token: str | None = None,
        size: int = 100,
    ) -> list[TicketOption]:
        arguments: dict[str, Any] = {
            "date": (
                travel_date.isoformat()
                if hasattr(travel_date, "isoformat")
                else str(travel_date)
            )
        }
        if start:
            arguments["start"] = start
        if end:
            arguments["end"] = end
        result = await self._call("search_tickets", arguments, token)
        data = result.get("data") or {}
        rows = data.get("list", []) if isinstance(data, dict) else []
        return [TicketOption.model_validate(item) for item in rows[:size]]

    async def search_tickets(
        self,
        constraints: SearchConstraints,
        token: str | None = None,
        size: int = 20,
    ) -> list[TicketOption]:
        if (
            constraints.date is None
            or constraints.start is None
            or constraints.end is None
        ):
            raise ValueError("date, start and end are required")
        return await self.list_tickets(
            constraints.date,
            constraints.start,
            constraints.end,
            token,
            size,
        )

    async def _call(
        self, name: str, arguments: dict[str, Any], token: str | None
    ) -> dict[str, Any]:
        headers = {"token": token} if token else None
        try:
            async with sse_client(
                self._url,
                headers=headers,
                timeout=self._timeout,
                sse_read_timeout=max(60, self._timeout),
            ) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    response = await session.call_tool(name, arguments=arguments)
        except Exception as exc:
            raise BusinessApiError(f"MCP工具调用失败: {exc}") from exc

        if response.isError:
            raise BusinessApiError(f"MCP工具返回失败: {self._text(response.content)}")
        raw = response.structuredContent or self._text(response.content)
        if isinstance(raw, dict):
            return raw
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"data": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"success": True, "data": raw}

    @staticmethod
    def _text(content: list[Any]) -> str:
        return "".join(
            block.text for block in content if isinstance(block, TextContent)
        )
