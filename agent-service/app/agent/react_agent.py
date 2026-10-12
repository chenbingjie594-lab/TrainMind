from typing import Any, Literal

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agent.state import AgentState
from app.agent.tools.executor import TicketToolExecutor
from app.agent.tools.middleware import ModelMonitor
from app.agent.tools.schemas import AGENT_TOOLS
from app.config import Settings
from app.graphs.rule_ticket_search import RuleTicketSearchWorkflow
from app.model.factory import ChatModelFactory
from app.models.ticket import SearchConstraints, TicketOption
from app.rag.knowledge import KnowledgeService
from app.services.constraint_extractor import ConstraintExtractor
from app.tools.business_client import BusinessApiClient
from app.utils.prompt_loader import load_system_prompt


class ReactAgent:
    """TrainMind ReAct Agent: model reasoning and isolated read-only tools."""

    def __init__(
        self,
        settings: Settings,
        extractor: ConstraintExtractor,
        business_client: BusinessApiClient,
        knowledge_service: KnowledgeService | None = None,
    ) -> None:
        self._settings = settings
        self._tools = TicketToolExecutor(
            settings, business_client, knowledge_service
        )
        self._agent_model = ChatModelFactory.create(settings, AGENT_TOOLS)
        if self._agent_model is not None:
            self.compiled = self._build_react_graph()
        else:
            self.compiled = RuleTicketSearchWorkflow(
                settings, extractor, business_client
            ).compiled

    def _build_react_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("agent", self._call_model)
        graph.add_node("tools", self._tools.execute)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges(
            "agent", self._route_after_model, {"tools": "tools", "end": END}
        )
        graph.add_edge("tools", "agent")
        return graph.compile()

    async def execute(self, state: AgentState) -> dict[str, Any]:
        """Run one conversation turn through the selected Agent workflow."""

        return await self.compiled.ainvoke(state)

    async def _call_model(self, state: AgentState) -> dict[str, Any]:
        messages = list(state.get("messages", []))
        ModelMonitor.before(len(messages))
        response = await self._agent_model.ainvoke(
            [SystemMessage(content=load_system_prompt()), *messages]
        )
        result: dict[str, Any] = {
            "messages": [*messages, response],
            "trace": self._append_trace(
                state,
                "agent",
                "SUCCESS",
                {"toolCalls": [call["name"] for call in response.tool_calls]},
            ),
        }
        if not response.tool_calls:
            constraints = SearchConstraints.model_validate(
                state.get("constraints") or {}
            )
            missing = constraints.missing_required()
            result.update(
                answer=self._message_text(response),
                missing_fields=missing,
                status="NEED_MORE_INFO" if missing else "COMPLETED",
            )
        return result

    @staticmethod
    def _route_after_model(state: AgentState) -> Literal["tools", "end"]:
        messages = state.get("messages", [])
        last = messages[-1] if messages else None
        return "tools" if isinstance(last, AIMessage) and last.tool_calls else "end"

    # Compatibility helpers retained for existing tests and callers while the
    # implementation itself now lives in the tool layer.
    async def _execute_tools(self, state: AgentState) -> dict[str, Any]:
        return await self._tools.execute(state)

    @staticmethod
    def _catalog_item(ticket: TicketOption) -> dict[str, Any]:
        return TicketToolExecutor.catalog_item(ticket)

    def _validate_model_selections(
        self,
        selections: list[dict[str, Any]],
        catalog: list[dict[str, Any]],
        constraints: SearchConstraints,
    ):
        return self._tools.validate_selections(selections, catalog, constraints)

    @staticmethod
    def _message_text(message: AIMessage) -> str:
        if isinstance(message.content, str):
            return message.content
        return "".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item)
            for item in message.content
        )

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
