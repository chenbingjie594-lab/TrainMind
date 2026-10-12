from typing import Any

from pydantic import BaseModel, Field

from app.models.ticket import ItineraryOption, SearchConstraints, TicketOption


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, alias="conversationId")
    message: str = Field(min_length=1, max_length=2000)

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    conversation_id: str = Field(alias="conversationId")
    message: str
    status: str
    constraints: SearchConstraints
    missing_fields: list[str] = Field(default_factory=list, alias="missingFields")
    tickets: list[TicketOption] = Field(default_factory=list)
    itineraries: list[ItineraryOption] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
