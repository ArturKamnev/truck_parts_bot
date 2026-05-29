from __future__ import annotations

import logging
from collections.abc import Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import AIMessage
from app.services.knowledge_service import KnowledgeService
from app.services.settings_service import SettingsService
from app.utils.enums import AIMessageRole
from app.utils.exceptions import AIServiceError

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class AIService:
    def __init__(
        self,
        settings: Settings,
        settings_service: SettingsService,
        knowledge_service: KnowledgeService,
    ) -> None:
        self._settings = settings
        self._settings_service = settings_service
        self._knowledge_service = knowledge_service

    async def save_message(
        self,
        session: AsyncSession,
        *,
        customer_id: int,
        role: AIMessageRole,
        content: str,
        model_id: str | None = None,
    ) -> AIMessage:
        message = AIMessage(
            customer_id=customer_id,
            role=role.value,
            content=content,
            model_id=model_id,
        )
        session.add(message)
        await session.flush()
        return message

    async def get_recent_history(
        self, session: AsyncSession, *, customer_id: int
    ) -> list[AIMessage]:
        stmt = (
            select(AIMessage)
            .where(AIMessage.customer_id == customer_id)
            .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
            .limit(self._settings.ai_history_limit)
        )
        rows = list(await session.scalars(stmt))
        rows.reverse()
        return rows

    async def answer(self, session: AsyncSession, *, customer_id: int) -> tuple[str, str]:
        model_id = await self._settings_service.get_active_model(session)
        history = await self.get_recent_history(session, customer_id=customer_id)
        messages = self._build_messages(history)
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-Title": self._settings.openrouter_app_name,
        }
        if self._settings.openrouter_site_url:
            headers["HTTP-Referer"] = self._settings.openrouter_site_url

        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 700,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(OPENROUTER_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except httpx.TimeoutException as exc:
            logger.warning("OpenRouter timeout for customer_id=%s", customer_id)
            raise AIServiceError("timeout") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "OpenRouter HTTP error status=%s customer_id=%s body=%s",
                exc.response.status_code,
                customer_id,
                exc.response.text[:500],
            )
            raise AIServiceError("http_error") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.exception("Malformed OpenRouter response for customer_id=%s", customer_id)
            raise AIServiceError("malformed_response") from exc

        if not isinstance(content, str) or not content.strip():
            logger.warning("Empty OpenRouter answer for customer_id=%s", customer_id)
            raise AIServiceError("empty_response")

        return content.strip(), model_id

    def _build_messages(self, history: Sequence[AIMessage]) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self._knowledge_service.build_system_context()}]
        for item in history:
            if item.role in {AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value}:
                messages.append({"role": item.role, "content": item.content})
        return messages
