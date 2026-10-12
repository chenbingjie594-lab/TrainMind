from __future__ import annotations

from datetime import date as Date
from datetime import time as Time
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SeatType(StrEnum):
    FIRST_CLASS = "YDZ"
    SECOND_CLASS = "EDZ"
    SOFT_SLEEPER = "RW"
    HARD_SLEEPER = "YW"


class SearchConstraints(BaseModel):
    date: Date | None = None
    start: str | None = None
    end: str | None = None
    depart_after: Time | None = Field(default=None, alias="departAfter")
    arrival_before: Time | None = Field(default=None, alias="arrivalBefore")
    seat_types: list[SeatType] = Field(default_factory=list, alias="seatTypes")
    max_price: Decimal | None = Field(default=None, ge=0, alias="maxPrice")

    model_config = {"populate_by_name": True}

    @field_validator("start", "end", mode="before")
    @classmethod
    def strip_station(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().removesuffix("站")
        return cleaned or None

    def merge(self, newer: "SearchConstraints") -> "SearchConstraints":
        current = self.model_dump()
        updates = newer.model_dump(exclude_none=True)
        if not newer.seat_types:
            updates.pop("seat_types", None)
        current.update(updates)
        return SearchConstraints.model_validate(current)

    def missing_required(self) -> list[str]:
        labels = {"date": "出发日期", "start": "出发站", "end": "到达站"}
        return [label for field, label in labels.items() if getattr(self, field) is None]


class TicketOption(BaseModel):
    id: str | None = None
    train_code: str = Field(alias="trainCode")
    date: Date
    start: str
    end: str
    start_time: str = Field(alias="startTime")
    end_time: str = Field(alias="endTime")
    ydz: int | None = None
    ydz_price: Decimal | None = Field(default=None, alias="ydzPrice")
    edz: int | None = None
    edz_price: Decimal | None = Field(default=None, alias="edzPrice")
    rw: int | None = None
    rw_price: Decimal | None = Field(default=None, alias="rwPrice")
    yw: int | None = None
    yw_price: Decimal | None = Field(default=None, alias="ywPrice")
    recommendation: str | None = None

    model_config = {"populate_by_name": True}


class ItineraryType(StrEnum):
    DIRECT = "DIRECT"
    TRANSFER = "TRANSFER"
    ALTERNATIVE_DATE = "ALTERNATIVE_DATE"
    ALTERNATIVE_STATION = "ALTERNATIVE_STATION"


class ItineraryOption(BaseModel):
    itinerary_type: ItineraryType = Field(alias="itineraryType")
    legs: list[TicketOption] = Field(min_length=1, max_length=2)
    transfer_station: str | None = Field(default=None, alias="transferStation")
    transfer_minutes: int | None = Field(default=None, alias="transferMinutes")
    total_minutes: int = Field(alias="totalMinutes")
    total_price: Decimal | None = Field(default=None, alias="totalPrice")
    recommendation: str

    model_config = {"populate_by_name": True}
