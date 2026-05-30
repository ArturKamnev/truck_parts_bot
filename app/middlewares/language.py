from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models import User
from app.i18n.translator import detect_language_code

logger = logging.getLogger(__name__)


class LanguageAutoDetectMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        if from_user and not from_user.is_bot:
            async with SessionLocal() as session:
                stmt = select(User).where(User.telegram_user_id == from_user.id)
                user = await session.scalar(stmt)
                if user:
                    if not user.preferred_language or not user.preferred_language.strip():
                        lang = detect_language_code(from_user.language_code)
                        user.preferred_language = lang
                        await session.commit()
                        logger.info(
                            "Auto-detected language for user %s: %s (tg language code: %s)",
                            from_user.id,
                            lang,
                            from_user.language_code
                        )
        return await handler(event, data)
