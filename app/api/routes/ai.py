from __future__ import annotations

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_ai_service
from app.db.models import User, AIMessage
from app.db.session import get_session
from app.services.ai_service import AIService
from app.utils.enums import AIMessageRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)


class AIChatResponse(BaseModel):
    response: str
    model_id: str


class AIMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    model_id: str | None
    created_at: datetime


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(
    req: AIChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ai_service: AIService = Depends(get_ai_service),
) -> AIChatResponse:
    """
    Handles AI chat queries for authenticated users, preserving context history in the DB.
    """
    # 1. Save user query in DB
    await ai_service.save_message(
        session,
        customer_id=current_user.id,
        role=AIMessageRole.USER,
        content=req.message,
    )
    await session.commit()
    
    # 2. Query AI completion response
    try:
        response_text, model_id = await ai_service.answer(session, customer_id=current_user.id)
    except Exception as exc:
        logger.warning("AI chat completion failed for customer_id=%s: %s", current_user.id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось получить ответ ИИ. Попробуйте еще раз.",
        )
        
    # 3. Save assistant response in DB
    await ai_service.save_message(
        session,
        customer_id=current_user.id,
        role=AIMessageRole.ASSISTANT,
        content=response_text,
        model_id=model_id,
    )
    await session.commit()
    
    return AIChatResponse(response=response_text, model_id=model_id)


@router.get("/history", response_model=list[AIMessageResponse])
async def ai_history(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AIMessageResponse]:
    """
    Returns the recent AI assistant chat history for the authenticated user.
    """
    stmt = (
        select(AIMessage)
        .where(AIMessage.customer_id == current_user.id)
        .order_by(AIMessage.id.desc())
        .limit(50)
    )
    result = await session.scalars(stmt)
    messages = list(result.all())
    messages.reverse() # chronologically ascending order for UI rendering
    
    return [
        AIMessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            model_id=msg.model_id,
            created_at=msg.created_at,
        )
        for msg in messages
    ]
