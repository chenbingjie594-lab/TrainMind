import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from langchain_core.messages import ToolMessage

from app.agent.state import AgentState
from app.agent.tools.middleware import ToolMonitor
from app.config import Settings
from app.models.ticket import (
    ItineraryOption,
    ItineraryType,
    SearchConstraints,
    SeatType,
    TicketOption,
)
from app.rag.knowledge import KnowledgeService
from app.tools.business_client import BusinessApiClient, BusinessApiError


class TicketToolExecutor:
    """Execute Agent-selected tools; never make itinerary decisions for the model."""

    def __init__(
        self,
        settings: Settings,
        business_client: BusinessApiClient,
        knowledge_service: KnowledgeService | None = None,
    ) -> None:
        self._settings = settings
        self._business = business_client
        self._knowledge = knowledge_service
        self._monitor = ToolMonitor()

    async def execute(self, state: AgentState) -> dict[str, Any]:
        messages = list(state.get("messages", []))
        last = messages[-1]
        tool_messages: list[ToolMessage] = []
        constraints = SearchConstraints.model_validate(state.get("constraints") or {})
        tickets = list(state.get("tickets", []))
        catalog = list(state.get("ticket_catalog", []))
        itineraries = list(state.get("itineraries", []))
        trace = list(state.get("trace", []))

        for call in last.tool_calls:
            name, args = call["name"], call.get("args") or {}
            self._monitor.before(name, args)
            try:
                if name == "search_stations":
                    result: Any = await self._business.search_stations(
                        str(args["keyword"]), token=state.get("token")
                    )
                elif name == "search_tickets":
                    requested = SearchConstraints.model_validate(args)
                    if requested.date is None:
                        raise ValueError("查询余票必须提供日期")
                    raw = await self._business.list_tickets(
                        requested.date,
                        start=requested.start,
                        end=requested.end,
                        token=state.get("token"),
                        size=100,
                    )
                    found = [self.catalog_item(item) for item in raw]
                    catalog = self.merge_catalog(catalog, found)
                    tickets = found if requested.start and requested.end else []
                    if requested.start and requested.end:
                        constraints = constraints.merge(requested)
                    result = {"count": len(found), "tickets": found}
                elif name == "select_itineraries":
                    plans = self.validate_selections(
                        args.get("plans") or [], catalog, constraints
                    )
                    itineraries = [
                        item.model_dump(mode="json", by_alias=True) for item in plans
                    ]
                    tickets = []
                    result = {"count": len(itineraries), "itineraries": itineraries}
                elif name == "search_knowledge":
                    result = (
                        await self._knowledge.search(str(args["query"]))
                        if self._knowledge is not None
                        else {"error": "知识库未启用", "citations": []}
                    )
                else:
                    raise ValueError(f"不支持的工具: {name}")
                status = "SUCCESS"
                self._monitor.success(name, result)
            except (BusinessApiError, KeyError, ValueError) as exc:
                result, status = {"error": str(exc)}, "FAILED"
                self._monitor.failure(name, exc)

            tool_messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False, default=str),
                    tool_call_id=call["id"],
                    name=name,
                )
            )
            trace.append(
                {"node": name, "status": status, "detail": self.trace_detail(result)}
            )

        return {
            "messages": [*messages, *tool_messages],
            "constraints": constraints.model_dump(mode="json", by_alias=True),
            "missing_fields": constraints.missing_required(),
            "tickets": tickets,
            "ticket_catalog": catalog,
            "itineraries": itineraries,
            "trace": trace,
        }

    @staticmethod
    def catalog_item(ticket: TicketOption) -> dict[str, Any]:
        item = ticket.model_dump(mode="json", by_alias=True)
        item["ticketRef"] = ticket.id or (
            f"{ticket.date.isoformat()}|{ticket.train_code}|"
            f"{ticket.start}|{ticket.end}|{ticket.start_time}"
        )
        return item

    @staticmethod
    def merge_catalog(
        current: list[dict[str, Any]], found: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        merged = {item["ticketRef"]: item for item in current}
        merged.update({item["ticketRef"]: item for item in found})
        return list(merged.values())

    def validate_selections(
        self,
        selections: list[dict[str, Any]],
        catalog: list[dict[str, Any]],
        constraints: SearchConstraints,
    ) -> list[ItineraryOption]:
        by_ref = {item["ticketRef"]: item for item in catalog}
        result: list[ItineraryOption] = []
        for selected in selections[: self._settings.max_results]:
            refs = selected.get("ticketRefs") or []
            if not 1 <= len(refs) <= 2:
                raise ValueError("每个推荐方案必须引用一程或两程真实车票")
            if any(ref not in by_ref for ref in refs):
                raise ValueError("推荐方案引用了未查询到的车票")
            legs = [TicketOption.model_validate(by_ref[ref]) for ref in refs]
            itinerary_type = ItineraryType(selected["itineraryType"])
            transfer_station = None
            transfer_minutes = None
            if len(legs) == 2:
                if itinerary_type != ItineraryType.TRANSFER:
                    raise ValueError("两程方案必须标记为 TRANSFER")
                if legs[0].end != legs[1].start:
                    raise ValueError("两程车票的中转站不一致")
                transfer_minutes = self.connection_minutes(legs[0], legs[1])
                if transfer_minutes < 20 or transfer_minutes > 240:
                    raise ValueError("换乘时间必须在 20 到 240 分钟之间")
                transfer_station = legs[0].end
            elif itinerary_type == ItineraryType.TRANSFER:
                raise ValueError("TRANSFER 方案必须包含两程车票")

            prices = [
                min(self.candidate_prices(leg, constraints.seat_types))
                for leg in legs
                if self.candidate_prices(leg, constraints.seat_types)
            ]
            result.append(
                ItineraryOption(
                    itineraryType=itinerary_type,
                    legs=legs,
                    transferStation=transfer_station,
                    transferMinutes=transfer_minutes,
                    totalMinutes=self.journey_minutes(legs[0], legs[-1]),
                    totalPrice=(
                        sum(prices, Decimal("0"))
                        if len(prices) == len(legs)
                        else None
                    ),
                    recommendation=str(selected["recommendation"]),
                )
            )
        return result

    @staticmethod
    def ticket_datetime(ticket: TicketOption, field: str) -> datetime:
        value = ticket.start_time if field == "start" else ticket.end_time
        return datetime.combine(
            ticket.date, datetime.strptime(value, "%H:%M:%S").time()
        )

    @classmethod
    def connection_minutes(cls, first: TicketOption, second: TicketOption) -> int:
        delta = cls.ticket_datetime(second, "start") - cls.ticket_datetime(first, "end")
        return int(delta.total_seconds() // 60)

    @classmethod
    def journey_minutes(cls, first: TicketOption, last: TicketOption) -> int:
        delta = cls.ticket_datetime(last, "end") - cls.ticket_datetime(first, "start")
        return int(delta.total_seconds() // 60)

    @staticmethod
    def candidate_prices(
        ticket: TicketOption, seats: list[SeatType]
    ) -> list[Decimal]:
        mapping = {
            SeatType.FIRST_CLASS: (ticket.ydz, ticket.ydz_price),
            SeatType.SECOND_CLASS: (ticket.edz, ticket.edz_price),
            SeatType.SOFT_SLEEPER: (ticket.rw, ticket.rw_price),
            SeatType.HARD_SLEEPER: (ticket.yw, ticket.yw_price),
        }
        selected = seats or list(mapping)
        return [
            price
            for seat in selected
            for count, price in [mapping[seat]]
            if count is not None and count > 0 and price is not None
        ]

    @staticmethod
    def trace_detail(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return {
                key: value
                for key, value in result.items()
                if key not in {"tickets", "itineraries"}
            }
        if isinstance(result, list):
            return {"count": len(result)}
        return {}
