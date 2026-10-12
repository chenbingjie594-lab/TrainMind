import logging
from typing import Any


logger = logging.getLogger(__name__)


class ToolMonitor:
    """Small middleware boundary for tool tracing and error observability."""

    @staticmethod
    def before(name: str, args: dict[str, Any]) -> None:
        logger.info("Agent调用工具 %s，参数=%s", name, args)

    @staticmethod
    def success(name: str, result: Any) -> None:
        count = len(result) if isinstance(result, list) else None
        if isinstance(result, dict):
            count = result.get("count")
        logger.info("Agent工具 %s 调用成功，结果数量=%s", name, count)

    @staticmethod
    def failure(name: str, exc: Exception) -> None:
        logger.warning("Agent工具 %s 调用失败：%s", name, exc)


class ModelMonitor:
    @staticmethod
    def before(message_count: int) -> None:
        logger.info("ReAct Agent 即将调用模型，消息数=%s", message_count)
