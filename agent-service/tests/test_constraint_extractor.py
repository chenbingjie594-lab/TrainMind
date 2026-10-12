from datetime import date

import pytest

from app.config import Settings
from app.models.ticket import SearchConstraints, SeatType
from app.services.constraint_extractor import ConstraintExtractor


@pytest.mark.asyncio
async def test_extract_complete_chinese_query() -> None:
    extractor = ConstraintExtractor(Settings(llm_enabled=False))
    result = await extractor.extract(
        "帮我查2026-07-17从上海到南京的二等座，最晚22点到，价格不超过200元",
        SearchConstraints(),
    )

    assert result.date == date(2026, 7, 17)
    assert result.start == "上海"
    assert result.end == "南京"
    assert result.arrival_before.hour == 22
    assert result.seat_types == [SeatType.SECOND_CLASS]
    assert result.max_price == 200


@pytest.mark.asyncio
async def test_merge_multi_turn_constraints() -> None:
    extractor = ConstraintExtractor(Settings(llm_enabled=False))
    first = await extractor.extract("从上海到南京", SearchConstraints())
    second = await extractor.extract("2026-07-17出发，要二等座", first)

    assert second.start == "上海"
    assert second.end == "南京"
    assert second.date == date(2026, 7, 17)
    assert second.seat_types == [SeatType.SECOND_CLASS]

