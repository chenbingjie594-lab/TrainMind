import json
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from app.config import Settings
from app.models.ticket import SearchConstraints, SeatType


class ConstraintExtractor:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        if settings.llm_enabled and settings.llm_api_key:
            # 模型 SDK 按需加载，默认规则模式不承担额外启动开销。
            from langchain_openai import ChatOpenAI

            self._model = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0,
                timeout=settings.llm_timeout_seconds,
                max_retries=1,
                extra_body={"enable_thinking": False},
            ).with_structured_output(
                SearchConstraints,
                method="function_calling",
            )

    async def extract(
        self, message: str, current: SearchConstraints
    ) -> SearchConstraints:
        if self._model is not None:
            from langchain_core.messages import HumanMessage, SystemMessage

            extracted = await self._model.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "你是火车票查询参数提取器。只提取用户明确给出的信息。"
                            "日期基准是 " + date.today().isoformat() + "。"
                            "车站名去掉末尾的站。座席编码：一等座 YDZ，二等座 EDZ，"
                            "软卧 RW，硬卧 YW。不要猜测缺失字段。"
                        )
                    ),
                    HumanMessage(
                        content=json.dumps(
                            {
                                "current": current.model_dump(mode="json", by_alias=True),
                                "message": message,
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            return current.merge(extracted)
        return current.merge(self._rule_extract(message))

    def _rule_extract(self, message: str) -> SearchConstraints:
        data: dict = {}
        parsed_date = self._parse_date(message)
        if parsed_date:
            data["date"] = parsed_date

        route_patterns = [
            r"从(?P<start>[\u4e00-\u9fa5A-Za-z]+?)(?:站)?(?:出发)?(?:到|去|前往)(?P<end>[\u4e00-\u9fa5A-Za-z]+?)(?:站)?(?:的|，|,|\s|$)",
            r"(?P<start>[\u4e00-\u9fa5A-Za-z]+?)(?:站)?(?:到|去)(?P<end>[\u4e00-\u9fa5A-Za-z]+?)(?:站)?(?:的|，|,|\s|$)",
        ]
        for pattern in route_patterns:
            match = re.search(pattern, message)
            if match:
                data["start"] = match.group("start")
                data["end"] = match.group("end")
                break

        seat_types = []
        for keyword, code in {
            "一等座": SeatType.FIRST_CLASS,
            "二等座": SeatType.SECOND_CLASS,
            "软卧": SeatType.SOFT_SLEEPER,
            "硬卧": SeatType.HARD_SLEEPER,
        }.items():
            if keyword in message:
                seat_types.append(code)
        if seat_types:
            data["seat_types"] = seat_types

        price_match = re.search(r"(?:不超过|最多|低于|小于|预算)\s*(\d+(?:\.\d+)?)\s*元?", message)
        if price_match:
            data["max_price"] = Decimal(price_match.group(1))

        arrival_match = re.search(r"(?:最晚|在)?\s*(\d{1,2})(?:[:：点时](\d{1,2})?)?\s*(?:前)?到", message)
        if arrival_match:
            data["arrival_before"] = self._to_time(arrival_match)

        depart_match = re.search(r"(?:最早|在)?\s*(\d{1,2})(?:[:：点时](\d{1,2})?)?\s*(?:后|以后|之后)(?:出发|走)?", message)
        if depart_match:
            data["depart_after"] = self._to_time(depart_match)

        return SearchConstraints.model_validate(data)

    @staticmethod
    def _to_time(match: re.Match) -> time:
        return time(int(match.group(1)), int(match.group(2) or 0))

    @staticmethod
    def _parse_date(message: str) -> date | None:
        today = date.today()
        full = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?", message)
        if full:
            return date(int(full.group(1)), int(full.group(2)), int(full.group(3)))
        short = re.search(r"(?<!\d)(\d{1,2})月(\d{1,2})日?", message)
        if short:
            candidate = date(today.year, int(short.group(1)), int(short.group(2)))
            return candidate if candidate >= today else candidate.replace(year=today.year + 1)
        if "后天" in message:
            return today + timedelta(days=2)
        if "明天" in message:
            return today + timedelta(days=1)
        if "今天" in message:
            return today
        weekday = re.search(r"(?:下)?周([一二三四五六日天])", message)
        if weekday:
            target = "一二三四五六日天".index(weekday.group(1))
            if target == 7:
                target = 6
            days = (target - today.weekday()) % 7
            if message[weekday.start():weekday.end()].startswith("下周"):
                days = days + 7 if days else 7
            elif days == 0:
                days = 7
            return today + timedelta(days=days)
        return None
