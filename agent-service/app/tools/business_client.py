from typing import Any

import httpx

from app.config import Settings
from app.models.ticket import SearchConstraints, TicketOption


class BusinessApiError(RuntimeError):
    pass


class BusinessApiClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.business_base_url.rstrip("/"),
            timeout=settings.request_timeout_seconds,
            transport=transport,
        )
    async def close(self) -> None:
        await self._client.aclose()

    async def search_stations(self, keyword: str, token: str | None = None) -> list[dict[str, Any]]:
        stations = await self.list_stations(token)
        lowered = keyword.lower()
        return [
            station
            for station in stations
            if lowered in str(station.get("name", "")).lower()
            or lowered in str(station.get("namePinyin", "")).lower()
            or lowered in str(station.get("namePy", "")).lower()
        ]

    async def list_stations(self, token: str | None = None) -> list[dict[str, Any]]:
        return await self._get("/business/station/query-all", token=token) or []

    async def search_tickets(
        self,
        constraints: SearchConstraints,
        token: str | None = None,
        size: int = 20,
    ) -> list[TicketOption]:
        if constraints.date is None or constraints.start is None or constraints.end is None:
            raise ValueError("date, start and end are required")
        content = await self._get(
            "/business/daily-train-ticket/query-list",
            params={
                "page": 1,
                "size": size,
                "date": constraints.date.isoformat(),
                "start": constraints.start,
                "end": constraints.end,
            },
            token=token,
        )
        return [TicketOption.model_validate(item) for item in (content or {}).get("list", [])]

    async def list_tickets(
        self,
        travel_date: Any,
        start: str | None = None,
        end: str | None = None,
        token: str | None = None,
        size: int = 500,
    ) -> list[TicketOption]:
        params: dict[str, Any] = {
            "page": 1,
            "size": size,
            "date": travel_date.isoformat() if hasattr(travel_date, "isoformat") else str(travel_date),
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        content = await self._get(
            "/business/daily-train-ticket/query-list", params=params, token=token
        )
        return [TicketOption.model_validate(item) for item in (content or {}).get("list", [])]

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> Any:
        headers = {"token": token} if token else {}
        try:
            response = await self._client.get(path, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BusinessApiError(f"业务服务调用失败: {exc}") from exc
        body = response.json()
        if not body.get("success", False):
            raise BusinessApiError(body.get("message") or "业务服务返回失败")
        return body.get("content")
