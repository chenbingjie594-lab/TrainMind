from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest, ChatResponse


router = APIRouter(prefix="/api/v1")


@router.get("/conversations/{conversation_id}")
async def conversation_history(
    conversation_id: str,
    request: Request,
    token: str | None = Header(default=None),
) -> dict:
    messages = await request.app.state.chat_service.history(conversation_id, token)
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found or expired")
    return {"conversationId": conversation_id, "messages": messages}


@router.post("/chat", response_model=ChatResponse, response_model_by_alias=True)
async def chat(
    body: ChatRequest,
    request: Request,
    token: str | None = Header(default=None),
) -> ChatResponse:
    return await request.app.state.chat_service.chat(body, token)


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    request: Request,
    token: str | None = Header(default=None),
) -> StreamingResponse:
    return StreamingResponse(
        request.app.state.chat_service.stream(body, token),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
