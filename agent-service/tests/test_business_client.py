import json

import httpx
import pytest

from app.config import Settings
from app.models.ticket import SearchConstraints
from app.tools.business_client import BusinessApiClient


@pytest.mark.asyncio
async def test_search_tickets_adapts_java_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["date"] == "2026-07-17"
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "success": True,
                    "content": {
                        "total": 1,
                        "list": [
                            {
                                "trainCode": "G101",
                                "date": "2026-07-17",
                                "start": "上海",
                                "end": "南京",
                                "startTime": "18:00:00",
                                "endTime": "19:30:00",
                                "ydz": 1,
                                "ydzPrice": 220,
                                "edz": 5,
                                "edzPrice": 140,
                                "rw": -1,
                                "rwPrice": 0,
                                "yw": -1,
                                "ywPrice": 0,
                            }
                        ],
                    },
                }
            ).encode(),
            headers={"content-type": "application/json"},
        )

    client = BusinessApiClient(
        Settings(business_base_url="http://test"),
        transport=httpx.MockTransport(handler),
    )
    result = await client.search_tickets(
        SearchConstraints(date="2026-07-17", start="上海", end="南京")
    )
    await client.close()

    assert len(result) == 1
    assert result[0].train_code == "G101"
    assert result[0].edz == 5

