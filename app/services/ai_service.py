from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import AIMessage, User
from app.services.knowledge_service import KnowledgeService
from app.services.settings_service import SettingsService
from app.utils.enums import AIMessageRole
from app.utils.exceptions import (
    AIServiceError,
    AIServiceInvalidAPIKeyError,
    AIServiceNetworkError,
    AIServiceRateLimitError,
    AIServiceTimeoutError,
    AIServiceUnavailableModelError,
)

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_TIMEOUT = httpx.Timeout(30.0, read=60.0)
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 700


@dataclass(frozen=True)
class ChatCompletionRequest:
    model_id: str
    messages: list[dict[str, str]]
    temperature: float
    max_tokens: int


async def iter_openrouter_sse_deltas(lines: AsyncIterator[str]) -> AsyncIterator[str]:
    data_lines: list[str] = []

    async for line in lines:
        stripped = line.strip()
        if not stripped:
            if _is_done_event(data_lines):
                return
            async for delta in _deltas_from_sse_data(data_lines):
                yield delta
            data_lines = []
            continue
        if stripped.startswith(":"):
            continue
        if stripped.startswith("data:"):
            data_lines.append(stripped.removeprefix("data:").strip())

    if not _is_done_event(data_lines):
        async for delta in _deltas_from_sse_data(data_lines):
            yield delta


async def _deltas_from_sse_data(data_lines: list[str]) -> AsyncIterator[str]:
    if not data_lines:
        return

    data = "\n".join(data_lines).strip()
    if not data or data == "[DONE]":
        return

    try:
        event = json.loads(data)
    except json.JSONDecodeError:
        logger.warning("Ignoring malformed OpenRouter stream event")
        return

    try:
        content = event["choices"][0]["delta"].get("content")
    except (KeyError, IndexError, TypeError, AttributeError):
        logger.warning("Ignoring OpenRouter stream event without text delta")
        return

    if isinstance(content, str) and content:
        yield content


def _is_done_event(data_lines: list[str]) -> bool:
    return "\n".join(data_lines).strip() == "[DONE]"


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

    @property
    def streaming_enabled(self) -> bool:
        return self._settings.ai_streaming_enabled

    @property
    def settings(self) -> Settings:
        return self._settings

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
            .limit(50)
        )
        rows = list(await session.scalars(stmt))
        rows.reverse()
        
        filtered = []
        for msg in rows:
            content = msg.content
            if not content or not content.strip():
                continue
            
            content_lower = content.lower()
            if "не удалось получить ответ" in content_lower:
                continue
            if "ответ был прерван" in content_lower:
                continue
            if "failed to process" in content_lower:
                continue
            if "service failed to" in content_lower:
                continue
            if "error placeholder" in content_lower:
                continue
                
            stripped = content.strip()
            if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, dict) and ("choices" in parsed or "error" in parsed or "id" in parsed or "model" in parsed):
                        continue
                except Exception:
                    pass
                    
            filtered.append(msg)
            
        return filtered[-10:]

    async def answer(self, session: AsyncSession, *, customer_id: int) -> tuple[str, str]:
        request = await self.prepare_chat_completion(session, customer_id=customer_id)
        payload = {
            "model": request.model_id,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
                response = await client.post(OPENROUTER_URL, json=payload, headers=self._headers())
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except httpx.TimeoutException as exc:
            logger.warning("OpenRouter timeout for customer_id=%s", customer_id)
            raise AIServiceTimeoutError("timeout") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "OpenRouter HTTP error status=%s customer_id=%s",
                exc.response.status_code,
                customer_id,
            )
            raise _exception_for_status(exc.response.status_code) from exc
        except httpx.RequestError as exc:
            logger.warning("OpenRouter network error for customer_id=%s", customer_id)
            raise AIServiceNetworkError("network_error") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.exception("Malformed OpenRouter response for customer_id=%s", customer_id)
            raise AIServiceError("malformed_response") from exc

        if not isinstance(content, str) or not content.strip():
            logger.warning("Empty OpenRouter answer for customer_id=%s", customer_id)
            raise AIServiceError("empty_response")

        return content.strip(), request.model_id

    async def prepare_chat_completion(
        self, session: AsyncSession, *, customer_id: int
    ) -> ChatCompletionRequest:
        model_id = await self._settings_service.get_active_model(session)
        history = await self.get_recent_history(session, customer_id=customer_id)
        
        user = await session.get(User, customer_id)
        lang = user.preferred_language if user else "ru"
        
        return ChatCompletionRequest(
            model_id=model_id,
            messages=self._build_messages(history, lang=lang),
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=DEFAULT_MAX_TOKENS,
        )

    async def stream_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature if temperature is not None else DEFAULT_TEMPERATURE,
            "max_tokens": max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
        }

        try:
            async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
                async with client.stream(
                    "POST", OPENROUTER_URL, json=payload, headers=self._headers()
                ) as response:
                    response.raise_for_status()
                    async for delta in iter_openrouter_sse_deltas(response.aiter_lines()):
                        if delta:
                            yield delta
        except httpx.TimeoutException as exc:
            logger.warning("OpenRouter stream timeout")
            raise AIServiceTimeoutError("timeout") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("OpenRouter stream HTTP error status=%s", exc.response.status_code)
            raise _exception_for_status(exc.response.status_code) from exc
        except httpx.RequestError as exc:
            logger.warning("OpenRouter stream network error")
            raise AIServiceNetworkError("network_error") from exc

    def _build_messages(self, history: Sequence[AIMessage], lang: str = "ru") -> list[dict[str, str]]:
        lang_names = {"ru": "Russian", "en": "English", "ky": "Kyrgyz"}
        lang_name = lang_names.get(lang, "Russian")
        
        system_context = self._knowledge_service.build_system_context().strip()
        system_content = (
            f"{system_context}\n\n"
            f"CRITICAL LANGUAGE INSTRUCTION: You MUST write your response in {lang_name}. This is the user's preferred language.\n"
            "If the information required to answer the user's question is not available in the company knowledge provided above, "
            "explicitly state that you do not have that information and suggest contacting a human manager."
        )
        
        messages = [{"role": "system", "content": system_content}]
        for item in history:
            if item.role in {AIMessageRole.USER.value, AIMessageRole.ASSISTANT.value}:
                messages.append({"role": item.role, "content": item.content})
        return messages

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-Title": self._settings.openrouter_app_name,
        }
        if self._settings.openrouter_site_url:
            headers["HTTP-Referer"] = self._settings.openrouter_site_url
        return headers


def _exception_for_status(status_code: int) -> AIServiceError:
    if status_code in {401, 403}:
        return AIServiceInvalidAPIKeyError("invalid_api_key")
    if status_code == 429:
        return AIServiceRateLimitError("rate_limit")
    if status_code in {400, 404}:
        return AIServiceUnavailableModelError("unavailable_model")
    if status_code in {408, 500, 502, 503, 504}:
        return AIServiceNetworkError("provider_unavailable")
    return AIServiceError("http_error")
