from app.services.session_store import HybridSessionStore, InMemorySessionStore


async def test_session_store_isolates_conversations_by_owner() -> None:
    store = InMemorySessionStore(ttl_minutes=60)

    await store.put("member-a", "conversation-1", {"status": "A"})
    await store.put("member-b", "conversation-1", {"status": "B"})

    assert await store.get("member-a", "conversation-1") == {"status": "A"}
    assert await store.get("member-b", "conversation-1") == {"status": "B"}
    assert await store.get("member-a", "missing") is None


async def test_hybrid_store_restores_cache_from_durable_store() -> None:
    cache = InMemorySessionStore(ttl_minutes=60)
    durable = InMemorySessionStore(ttl_minutes=60)
    store = HybridSessionStore(cache, durable)
    state = {"status": "COMPLETED", "display_messages": []}

    await durable.put("member-a", "conversation-1", state)

    assert await cache.get("member-a", "conversation-1") is None
    assert await store.get("member-a", "conversation-1") == state
    assert await cache.get("member-a", "conversation-1") == state
