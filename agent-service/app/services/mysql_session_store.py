from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    delete,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AgentConversation(Base):
    __tablename__ = "agent_conversation"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "conversation_id", name="uk_agent_conversation_owner"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AgentMessage(Base):
    __tablename__ = "agent_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_pk: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("agent_conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class MySqlSessionStore:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(
            database_url, pool_pre_ping=True, pool_recycle=1800
        )
        self._sessions = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    async def initialize(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def get(
        self, owner_id: str, conversation_id: str
    ) -> dict[str, Any] | None:
        async with self._sessions() as session:
            conversation = await self._find(session, owner_id, conversation_id)
            if conversation is None:
                return None
            result = dict(conversation.state_json)
            rows = await session.scalars(
                select(AgentMessage)
                .where(AgentMessage.conversation_pk == conversation.id)
                .order_by(AgentMessage.id)
            )
            display_messages = []
            for row in rows:
                message = dict(row.metadata_json)
                message.update(
                    {
                        "role": row.role,
                        "content": row.content,
                        "time": row.created_at.replace(tzinfo=UTC).isoformat(),
                    }
                )
                display_messages.append(message)
            result["display_messages"] = display_messages
            return result

    async def put(
        self, owner_id: str, conversation_id: str, state: dict[str, Any]
    ) -> None:
        durable_state = dict(state)
        display_messages = durable_state.pop("display_messages", [])
        async with self._sessions.begin() as session:
            conversation = await self._find(session, owner_id, conversation_id)
            if conversation is None:
                conversation = AgentConversation(
                    owner_id=owner_id,
                    conversation_id=conversation_id,
                    state_json=durable_state,
                )
                session.add(conversation)
                await session.flush()
            else:
                conversation.state_json = durable_state
                conversation.updated_at = datetime.utcnow()
                await session.execute(
                    delete(AgentMessage).where(
                        AgentMessage.conversation_pk == conversation.id
                    )
                )

            for message in display_messages:
                metadata = {
                    key: value
                    for key, value in message.items()
                    if key not in {"role", "content", "time"}
                }
                created_at = self._parse_time(message.get("time"))
                session.add(
                    AgentMessage(
                        conversation_pk=conversation.id,
                        role=message.get("role", "assistant"),
                        content=message.get("content", ""),
                        metadata_json=metadata,
                        created_at=created_at,
                    )
                )

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    async def _find(
        session: AsyncSession, owner_id: str, conversation_id: str
    ) -> AgentConversation | None:
        return await session.scalar(
            select(AgentConversation).where(
                AgentConversation.owner_id == owner_id,
                AgentConversation.conversation_id == conversation_id,
            )
        )

    @staticmethod
    def _parse_time(value: Any) -> datetime:
        if not isinstance(value, str):
            return datetime.utcnow()
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(UTC).replace(tzinfo=None)
            return parsed
        except ValueError:
            return datetime.utcnow()
