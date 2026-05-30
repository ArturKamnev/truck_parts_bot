from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message

from app.config import Settings

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096
SAFE_MESSAGE_LIMIT = 3900
THINKING_TEXT = "💭 Думаю..."


@dataclass(frozen=True)
class TelegramStreamRendererConfig:
    update_interval_seconds: float = 0.8
    min_chars: int = 80
    use_telegram_draft: bool = True


class TelegramPartialResponseRenderer:
    def __init__(self, config: TelegramStreamRendererConfig) -> None:
        self._config = config
        self._message: Message | None = None
        self._draft_supported: bool | None = None
        self._last_text = ""
        self._last_update_at = 0.0

    @classmethod
    def from_settings(cls, settings: Settings) -> TelegramPartialResponseRenderer:
        return cls(
            TelegramStreamRendererConfig(
                update_interval_seconds=settings.ai_stream_update_interval_seconds,
                min_chars=settings.ai_stream_min_chars,
                use_telegram_draft=settings.ai_stream_use_telegram_draft,
            )
        )

    async def start(self, message: Message, bot: Bot) -> None:
        if self._config.use_telegram_draft:
            self._draft_supported = await self._send_message_draft(
                bot=bot,
                chat_id=message.chat.id,
                text=THINKING_TEXT,
            )
            if self._draft_supported:
                self._last_text = ""
                self._last_update_at = time.monotonic()
                return

        self._draft_supported = False
        self._message = await message.answer(THINKING_TEXT, parse_mode=None)
        self._last_text = ""
        self._last_update_at = time.monotonic()

    async def render_partial(self, bot: Bot, chat_id: int, text: str) -> None:
        partial = _fit_single_message(text)
        if not partial:
            return

        now = time.monotonic()
        enough_text = len(partial) - len(self._last_text) >= self._config.min_chars
        enough_time = now - self._last_update_at >= self._config.update_interval_seconds
        if not enough_text and not enough_time:
            return

        if self._draft_supported:
            updated = await self._send_message_draft(bot=bot, chat_id=chat_id, text=partial)
            if updated:
                self._remember_update(partial, now)
                return
            self._draft_supported = False

        if self._message is None:
            self._message = await bot.send_message(
                chat_id=chat_id, text=THINKING_TEXT, parse_mode=None
            )

        try:
            await self._message.edit_text(partial, parse_mode=None)
            self._remember_update(partial, now)
        except TelegramAPIError as exc:
            logger.warning("Telegram stream edit failed: %s", exc.__class__.__name__)

    async def finalize(self, bot: Bot, chat_id: int, text: str, reply_markup: Any = None) -> None:
        chunks = split_telegram_text(text)
        if not chunks:
            return

        if self._message is not None:
            try:
                await self._message.edit_text(chunks[0], parse_mode=None, reply_markup=reply_markup)
            except TelegramAPIError as exc:
                logger.warning("Telegram final edit failed: %s", exc.__class__.__name__)
                await bot.send_message(
                    chat_id=chat_id, text=chunks[0], parse_mode=None, reply_markup=reply_markup
                )
        else:
            await bot.send_message(
                chat_id=chat_id, text=chunks[0], parse_mode=None, reply_markup=reply_markup
            )

        for chunk in chunks[1:]:
            await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=None)

    async def _send_message_draft(self, *, bot: Bot, chat_id: int, text: str) -> bool:
        token = getattr(bot, "token", None)
        if not token:
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessageDraft"
        payload = {"chat_id": chat_id, "text": _fit_single_message(text)}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                return bool(data.get("ok"))
            if response.status_code in {400, 404, 405}:
                logger.info("Telegram sendMessageDraft unsupported; using edit-message streaming")
                return False
            logger.warning("Telegram sendMessageDraft failed status=%s", response.status_code)
            return False
        except (httpx.RequestError, ValueError):
            logger.info("Telegram sendMessageDraft unavailable; using edit-message streaming")
            return False

    def _remember_update(self, text: str, updated_at: float) -> None:
        self._last_text = text
        self._last_update_at = updated_at


def split_telegram_text(text: str, limit: int = SAFE_MESSAGE_LIMIT) -> list[str]:
    remaining = text.strip()
    chunks: list[str] = []

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        split_at = max(
            remaining.rfind("\n\n", 0, limit),
            remaining.rfind("\n", 0, limit),
            remaining.rfind(" ", 0, limit),
        )
        if split_at < limit // 2:
            split_at = limit

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].strip()

    return chunks


def _fit_single_message(text: str) -> str:
    stripped = text.strip()
    if len(stripped) <= SAFE_MESSAGE_LIMIT:
        return stripped
    return stripped[: SAFE_MESSAGE_LIMIT - 1].rstrip() + "…"
