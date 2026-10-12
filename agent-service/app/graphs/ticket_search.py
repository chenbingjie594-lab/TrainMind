"""Backward-compatible import for the pre-refactor graph name."""

from app.agent.react_agent import ReactAgent
from app.agent.state import AgentState as TicketSearchState

TicketSearchGraph = ReactAgent

__all__ = ["TicketSearchGraph", "TicketSearchState"]
