import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any, Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError


class SessionStore(Protocol):
    async def get(self, owner_id: str, conversation_id: str) -> dict[str, Any] | None: ...

    async def put(
        self, owner_id: str, conversation_id: str, state: dict[str, Any]
    ) -> None: ...

    async def close(self) -> None: ...


class InMemorySessionStore:
    def __init__(self, ttl_minutes: int = 60) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._items: dict[str, tuple[datetime, dict[str, Any]]] = {}
        self._lock = RLock()

    @staticmethod
    def _key(owner_id: str, conversation_id: str) -> str:
        return f"{owner_id}:{conversation_id}"

    async def get(
        self, owner_id: str, conversation_id: str
    ) -> dict[str, Any] | None:
        key = self._key(owner_id, conversation_id)
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= datetime.now(UTC):
                self._items.pop(key, None)
                return None
            return deepcopy(value)

    async def put(
        self, owner_id: str, conversation_id: str, state: dict[str, Any]
    ) -> None:
        key = self._key(owner_id, conversation_id)
        with self._lock:
            self._items[key] = (
                datetime.now(UTC) + self._ttl,
                deepcopy(state),
            )

    async def close(self) -> None:
        return None


class RedisSessionStore:
    def __init__(
        self,
        redis_url: str,
        ttl_minutes: int = 60,
        key_prefix: str = "trainmind:agent:conversation",
    ) -> None:
        self._redis = Redis.from_url(redis_url, decode_responses=True)
        self._ttl_seconds = ttl_minutes * 60
        self._key_prefix = key_prefix.rstrip(":")

    def _key(self, owner_id: str, conversation_id: str) -> str:
        return f"{self._key_prefix}:{owner_id}:{conversation_id}"

    async def ping(self) -> None:
        await self._redis.ping()

    async def get(
        self, owner_id: str, conversation_id: str
    ) -> dict[str, Any] | None:
        value = await self._redis.get(self._key(owner_id, conversation_id))
        if value is None:
            return None
        # Reading an active conversation refreshes its sliding expiration time.
        await self._redis.expire(
            self._key(owner_id, conversation_id), self._ttl_seconds
        )
        return json.loads(value)

    async def put(
        self, owner_id: str, conversation_id: str, state: dict[str, Any]
    ) -> None:
        await self._redis.set(
            self._key(owner_id, conversation_id),
            json.dumps(state, ensure_ascii=False),
            ex=self._ttl_seconds,
        )

    async def close(self) -> None:
        await self._redis.aclose()


class HybridSessionStore:
    def __init__(
        self, cache: RedisSessionStore, durable_store: SessionStore
    ) -> None:
        self._cache = cache
        self._durable_store = durable_store

    async def get(
        self, owner_id: str, conversation_id: str
    ) -> dict[str, Any] | None:
        try:
            cached = await self._cache.get(owner_id, conversation_id)
        except RedisError:
            cached = None
        if cached is not None:
            return cached

        durable = await self._durable_store.get(owner_id, conversation_id)
        if durable is not None:
            try:
                await self._cache.put(owner_id, conversation_id, durable)
            except RedisError:
                pass
        return durable

    async def put(
        self, owner_id: str, conversation_id: str, state: dict[str, Any]
    ) -> None:
        # MySQL is the source of truth; Redis is only a recoverable cache.
        await self._durable_store.put(owner_id, conversation_id, state)
        try:
            await self._cache.put(owner_id, conversation_id, state)
        except RedisError:
            pass

    async def close(self) -> None:
        await self._cache.close()
        await self._durable_store.close()
