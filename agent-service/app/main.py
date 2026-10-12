from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import get_settings
from app.agent.react_agent import ReactAgent
from app.rag.rag_service import RagService
from app.services.chat_service import ChatService
from app.services.constraint_extractor import ConstraintExtractor
from app.services.mysql_session_store import MySqlSessionStore
from app.services.session_store import (
    HybridSessionStore,
    InMemorySessionStore,
    RedisSessionStore,
)
from app.tools.business_client import BusinessApiClient
from app.tools.business_client import BusinessApiError
from app.tools.mcp_ticket_client import McpTicketClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    business_client = (
        McpTicketClient(settings)
        if settings.mcp_enabled
        else BusinessApiClient(settings)
    )
    knowledge_service = RagService(settings)
    await knowledge_service.initialize()
    agent = ReactAgent(
        settings,
        ConstraintExtractor(settings),
        business_client,
        knowledge_service,
    )
    app.state.business_client = business_client
    store_mode = settings.session_store.lower()
    if store_mode in {"redis", "hybrid"}:
        session_store = RedisSessionStore(
            settings.redis_url,
            settings.session_ttl_minutes,
            settings.redis_key_prefix,
        )
        await session_store.ping()
        if store_mode == "hybrid":
            mysql_store = MySqlSessionStore(settings.mysql_url)
            await mysql_store.initialize()
            session_store = HybridSessionStore(session_store, mysql_store)
    else:
        session_store = InMemorySessionStore(settings.session_ttl_minutes)
    app.state.session_store = session_store
    app.state.agent = agent
    app.state.chat_service = ChatService(agent, session_store)
    yield
    await session_store.close()
    await knowledge_service.close()
    await business_client.close()


app = FastAPI(
    title="TrainMind Agent Service",
    version="0.2.0",
    description="TrainMind natural-language ticket search and recommendation agent.",
    lifespan=lifespan,
)
app.include_router(router)


@app.exception_handler(BusinessApiError)
async def business_api_error_handler(_, exc: BusinessApiError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={
            "code": "BUSINESS_SERVICE_UNAVAILABLE",
            "message": str(exc),
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    mode = "llm" if settings.llm_enabled and settings.llm_api_key else "rule"
    return {"status": "UP", "mode": mode}
