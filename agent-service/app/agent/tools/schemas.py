from typing import Any


SEARCH_STATIONS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_stations",
        "description": "按中文名、拼音或拼音首字母查询真实火车站。仅在站名不明确或需要确认站点时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "用户提到的城市或车站关键词"}
            },
            "required": ["keyword"],
        },
    },
}

SEARCH_TICKETS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_tickets",
        "description": (
            "查询真实余票数据。日期必填，出发站和到达站可选。"
            "查直达时同时传 start/end；寻找中转时可以只传 start 查询第一程，"
            "或只传 end 查询第二程。日期、替代站和调用次数由 Agent 自行决策。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "出发日期，格式 YYYY-MM-DD"},
                "start": {"type": "string", "description": "出发站名，不带‘站’字"},
                "end": {"type": "string", "description": "到达站名，不带‘站’字"},
                "departAfter": {"type": "string", "description": "最早出发时间，格式 HH:MM:SS"},
                "arrivalBefore": {"type": "string", "description": "最晚到达时间，格式 HH:MM:SS"},
                "seatTypes": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["YDZ", "EDZ", "RW", "YW"]},
                    "description": "一等座YDZ、二等座EDZ、软卧RW、硬卧YW",
                },
                "maxPrice": {"type": "number", "minimum": 0, "description": "最高预算，单位元"},
            },
            "required": ["date"],
        },
    },
}

SELECT_ITINERARIES_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "select_itineraries",
        "description": (
            "从此前 search_tickets 返回的真实车票中提交最终推荐方案。"
            "Agent 负责选择日期、车站、直达或中转、排序并编写推荐理由；"
            "只能引用工具结果里的 ticketRef，不能虚构车次。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "plans": {
                    "type": "array",
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "properties": {
                            "itineraryType": {
                                "type": "string",
                                "enum": ["DIRECT", "TRANSFER", "ALTERNATIVE_DATE", "ALTERNATIVE_STATION"],
                            },
                            "ticketRefs": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 2,
                                "items": {"type": "string"},
                            },
                            "recommendation": {
                                "type": "string",
                                "description": "根据用户偏好给出的具体推荐理由",
                            },
                        },
                        "required": ["itineraryType", "ticketRefs", "recommendation"],
                    },
                }
            },
            "required": ["plans"],
        },
    },
}

SEARCH_KNOWLEDGE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": (
            "检索退票、改签、学生票、儿童票、行李和乘车须知知识库。"
            "票务规则问题必须先调用此工具，并依据返回证据回答和标注引用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "需要检索的票务规则问题"}
            },
            "required": ["query"],
        },
    },
}

AGENT_TOOLS = [
    SEARCH_STATIONS_TOOL,
    SEARCH_TICKETS_TOOL,
    SELECT_ITINERARIES_TOOL,
    SEARCH_KNOWLEDGE_TOOL,
]
