"""Optional FastAPI HTTP server for ConnectX Telecom Customer Support Bot.

Provides RESTful endpoints for chat completions, session resets, and health checks.
"""

from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
from chatbot.bot import get_or_create_bot, reset_session

app = FastAPI(
    title="ConnectX Support Chatbot API",
    description="REST API for ConnectX Telecom customer service assistant",
    version="1.0.0",
)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class ResetRequest(BaseModel):
    session_id: str = "default"


class ResetResponse(BaseModel):
    status: str
    message: str


@app.get("/health")
def health() -> dict:
    """Service health check."""
    return {"status": "ok", "service": "ConnectX Telecom Support Bot"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    """Chat endpoint supporting multi-turn sessions."""
    bot = get_or_create_bot(payload.session_id or "default")
    reply = bot.reply(payload.message)
    return ChatResponse(reply=reply, session_id=payload.session_id or "default")


@app.post("/reset", response_model=ResetResponse)
def reset_endpoint(payload: ResetRequest) -> ResetResponse:
    """Clears history for a given session."""
    reset_session(payload.session_id)
    return ResetResponse(
        status="ok",
        message=f"Session '{payload.session_id}' cleared successfully.",
    )
