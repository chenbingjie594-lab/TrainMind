from app.config import Settings
from app.graphs.ticket_search import TicketSearchGraph
from app.models.ticket import SearchConstraints, TicketOption
from app.services.constraint_extractor import ConstraintExtractor
from langchain_core.messages import AIMessage


class FakeBusinessClient:
    async def search_stations(self, keyword, token=None):
        return [{"name": keyword}]

    async def search_tickets(self, constraints, token=None, size=20):
        return [
            TicketOption(
                id="t1",
                trainCode="G101",
                date="2026-07-17",
                start="上海",
                end="南京",
                startTime="18:00:00",
                endTime="19:30:00",
                ydz=2,
                ydzPrice=220,
                edz=10,
                edzPrice=140,
                rw=-1,
                yw=-1,
            ),
            TicketOption(
                id="t2",
                trainCode="G103",
                date="2026-07-17",
                start="上海",
                end="南京",
                startTime="20:30:00",
                endTime="22:30:00",
                ydz=2,
                ydzPrice=210,
                edz=8,
                edzPrice=135,
                rw=-1,
                yw=-1,
            ),
        ]

    async def list_tickets(self, travel_date, start=None, end=None, token=None, size=100):
        tickets = await self.search_tickets(None, token, size)
        return [
            item for item in tickets
            if (start is None or item.start == start)
            and (end is None or item.end == end)
        ]


async def test_graph_asks_for_missing_fields() -> None:
    settings = Settings(llm_enabled=False)
    graph = TicketSearchGraph(
        settings, ConstraintExtractor(settings), FakeBusinessClient()
    )
    result = await graph.compiled.ainvoke(
        {
            "conversation_id": "1",
            "message": "我想查票",
            "constraints": SearchConstraints().model_dump(mode="json"),
            "trace": [],
        }
    )

    assert result["status"] == "NEED_MORE_INFO"
    assert "出发日期" in result["answer"]


async def test_graph_filters_by_time_seat_and_price() -> None:
    settings = Settings(llm_enabled=False)
    graph = TicketSearchGraph(
        settings, ConstraintExtractor(settings), FakeBusinessClient()
    )
    result = await graph.compiled.ainvoke(
        {
            "conversation_id": "1",
            "message": "查2026-07-17从上海到南京的二等座，最晚22点到，不超过200元",
            "constraints": {},
            "trace": [],
        }
    )

    assert result["status"] == "COMPLETED"
    assert len(result["tickets"]) == 1
    assert result["tickets"][0]["trainCode"] == "G101"


async def test_tool_call_executes_search_and_keeps_structured_result() -> None:
    settings = Settings(llm_enabled=False)
    graph = TicketSearchGraph(settings, ConstraintExtractor(settings), FakeBusinessClient())
    tool_call = {
        "name": "search_tickets",
        "args": {
            "date": "2026-07-17",
            "start": "上海",
            "end": "南京",
            "arrivalBefore": "22:00:00",
            "seatTypes": ["EDZ"],
            "maxPrice": 200,
        },
        "id": "call-1",
        "type": "tool_call",
    }

    result = await graph._execute_tools(
        {
            "messages": [AIMessage(content="", tool_calls=[tool_call])],
            "constraints": {},
            "trace": [],
        }
    )

    assert result["constraints"]["start"] == "上海"
    # LLM 模式下查询工具返回原始真实数据，不再由 Python 替模型排序推荐。
    assert len(result["tickets"]) == 2
    assert result["tickets"][0]["trainCode"] == "G101"
    assert result["trace"][-1]["node"] == "search_tickets"


async def test_model_can_select_and_recommend_from_real_ticket_refs() -> None:
    settings = Settings(llm_enabled=False)
    graph = TicketSearchGraph(settings, ConstraintExtractor(settings), FakeBusinessClient())
    catalog = [
        graph._catalog_item(item)
        for item in await FakeBusinessClient().search_tickets(None)
    ]
    tool_call = {
        "name": "select_itineraries",
        "args": {
            "plans": [
                {
                    "itineraryType": "DIRECT",
                    "ticketRefs": ["t2"],
                    "recommendation": "这趟价格更低，符合你的预算偏好",
                }
            ]
        },
        "id": "call-2",
        "type": "tool_call",
    }

    result = await graph._execute_tools(
        {
            "messages": [AIMessage(content="", tool_calls=[tool_call])],
            "constraints": {},
            "ticket_catalog": catalog,
            "trace": [],
        }
    )

    assert result["itineraries"][0]["legs"][0]["trainCode"] == "G103"
    assert result["itineraries"][0]["recommendation"] == "这趟价格更低，符合你的预算偏好"
