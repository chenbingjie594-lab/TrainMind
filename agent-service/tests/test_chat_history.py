from app.services.chat_service import ChatService
from app.services.session_store import InMemorySessionStore


async def test_history_is_restored_for_same_owner_only() -> None:
    store = InMemorySessionStore(ttl_minutes=60)
    service = ChatService(graph=None, sessions=store)  # type: ignore[arg-type]
    owner = service._owner_id("member-token")
    await store.put(
        owner,
        "conversation-1",
        {
            "display_messages": [
                {"role": "user", "content": "北京到上海", "time": None}
            ]
        },
    )

    assert await service.history("conversation-1", "member-token") == [
        {"role": "user", "content": "北京到上海", "time": None}
    ]
    assert await service.history("conversation-1", "another-token") is None
