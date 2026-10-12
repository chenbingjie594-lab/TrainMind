from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.agent.state import AgentState
from app.config import Settings
from app.models.ticket import SearchConstraints, SeatType, TicketOption
from app.services.constraint_extractor import ConstraintExtractor
from app.tools.business_client import BusinessApiClient


class RuleTicketSearchWorkflow:
    """Deterministic local fallback used when no LLM is configured."""

    def __init__(
        self,
        settings: Settings,
        extractor: ConstraintExtractor,
        business_client: BusinessApiClient,
    ) -> None:
        self._settings = settings
        self._extractor = extractor
        self._business = business_client
        self.compiled = self._build()

    def _build(self):
        graph = StateGraph(AgentState)
        graph.add_node("extract_constraints", self._extract_constraints)
        graph.add_node("ask_for_missing", self._ask_for_missing)
        graph.add_node("search_tickets", self._search_tickets)
        graph.add_node("rank_tickets", self._rank_tickets)
        graph.add_edge(START, "extract_constraints")
        graph.add_conditional_edges(
            "extract_constraints",
            self._route_after_extraction,
            {"ask": "ask_for_missing", "search": "search_tickets"},
        )
        graph.add_edge("ask_for_missing", END)
        graph.add_edge("search_tickets", "rank_tickets")
        graph.add_edge("rank_tickets", END)
        return graph.compile()

    async def _extract_constraints(self, state: AgentState) -> dict[str, Any]:
        current = SearchConstraints.model_validate(state.get("constraints") or {})
        constraints = await self._extractor.extract(state["message"], current)
        return {
            "constraints": constraints.model_dump(mode="json", by_alias=True),
            "missing_fields": constraints.missing_required(),
            "trace": self._append_trace(state, "extract_constraints", "SUCCESS"),
        }

    @staticmethod
    def _route_after_extraction(state: AgentState) -> Literal["ask", "search"]:
        return "ask" if state.get("missing_fields") else "search"

    async def _ask_for_missing(self, state: AgentState) -> dict[str, Any]:
        missing = state.get("missing_fields", [])
        answer = (
            f"请告诉我{missing[0]}。"
            if len(missing) == 1
            else "还需要补充" + "、".join(missing) + "。"
        )
        return {
            "answer": answer,
            "status": "NEED_MORE_INFO",
            "tickets": [],
            "trace": self._append_trace(state, "ask_for_missing", "SUCCESS"),
        }

    async def _search_tickets(self, state: AgentState) -> dict[str, Any]:
        constraints = SearchConstraints.model_validate(state["constraints"])
        tickets = await self._business.search_tickets(
            constraints, token=state.get("token")
        )
        return {
            "tickets": [
                item.model_dump(mode="json", by_alias=True) for item in tickets
            ],
            "trace": self._append_trace(
                state, "search_tickets", "SUCCESS", {"count": len(tickets)}
            ),
        }

    async def _rank_tickets(self, state: AgentState) -> dict[str, Any]:
        constraints = SearchConstraints.model_validate(state["constraints"])
        tickets = [
            TicketOption.model_validate(item) for item in state.get("tickets", [])
        ]
        selected = self._filter_and_rank(tickets, constraints)
        answer = (
            f"找到 {len(selected)} 个符合条件的车次，已按偏好为你排序。"
            if selected
            else "没有找到满足全部条件的车次，可以放宽时间、价格或席别条件后再试。"
        )
        return {
            "tickets": [
                item.model_dump(mode="json", by_alias=True) for item in selected
            ],
            "answer": answer,
            "status": "COMPLETED",
            "trace": self._append_trace(
                state, "rank_tickets", "SUCCESS", {"count": len(selected)}
            ),
        }

    def _filter_and_rank(
        self, tickets: list[TicketOption], constraints: SearchConstraints
    ) -> list[TicketOption]:
        filtered = [ticket for ticket in tickets if self._matches(ticket, constraints)]
        filtered.sort(key=lambda item: self._score(item, constraints))
        selected = filtered[: self._settings.max_results]
        for index, ticket in enumerate(selected):
            ticket.recommendation = self._recommendation(ticket, constraints, index)
        return selected

    @staticmethod
    def _matches(ticket: TicketOption, constraints: SearchConstraints) -> bool:
        start_time = datetime.strptime(ticket.start_time, "%H:%M:%S").time()
        end_time = datetime.strptime(ticket.end_time, "%H:%M:%S").time()
        if constraints.depart_after and start_time < constraints.depart_after:
            return False
        if constraints.arrival_before and end_time > constraints.arrival_before:
            return False
        if constraints.seat_types and not any(
            (RuleTicketSearchWorkflow._seat_count(ticket, seat) or 0) > 0
            for seat in constraints.seat_types
        ):
            return False
        if constraints.max_price is not None:
            prices = RuleTicketSearchWorkflow._candidate_prices(
                ticket, constraints.seat_types
            )
            if not prices or min(prices) > constraints.max_price:
                return False
        return True

    @staticmethod
    def _score(ticket: TicketOption, constraints: SearchConstraints) -> tuple:
        prices = RuleTicketSearchWorkflow._candidate_prices(
            ticket, constraints.seat_types
        )
        return (
            ticket.end_time,
            min(prices) if prices else Decimal("999999"),
            ticket.start_time,
        )

    @staticmethod
    def _seat_count(ticket: TicketOption, seat: SeatType) -> int | None:
        return {
            SeatType.FIRST_CLASS: ticket.ydz,
            SeatType.SECOND_CLASS: ticket.edz,
            SeatType.SOFT_SLEEPER: ticket.rw,
            SeatType.HARD_SLEEPER: ticket.yw,
        }[seat]

    @staticmethod
    def _candidate_prices(
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
    def _recommendation(
        ticket: TicketOption, constraints: SearchConstraints, index: int
    ) -> str:
        reasons = ["综合偏好最匹配"] if index == 0 else []
        if constraints.arrival_before:
            reasons.append(f"{ticket.end_time[:5]} 到达")
        prices = RuleTicketSearchWorkflow._candidate_prices(
            ticket, constraints.seat_types
        )
        if prices:
            reasons.append(f"可选席位最低 {min(prices)} 元")
        return "；".join(reasons) or "当前有可售席位"

    @staticmethod
    def _append_trace(
        state: AgentState,
        node: str,
        status: str,
        detail: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            *state.get("trace", []),
            {"node": node, "status": status, "detail": detail or {}},
        ]
