from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.services.authorization_service import AuthorizationService
from app.db.session import SessionLocal


class IsOwner(BaseFilter):
    async def __call__(
        self,
        event: Message | CallbackQuery,
        authorization: AuthorizationService,
    ) -> bool:
        user_id = _telegram_user_id(event)
        async with SessionLocal() as session:
            role = await authorization.detect_role_db(user_id, session)
        return role in {"owner", "co_owner"}


class IsSupport(BaseFilter):
    async def __call__(
        self,
        event: Message | CallbackQuery,
        authorization: AuthorizationService,
    ) -> bool:
        user_id = _telegram_user_id(event)
        async with SessionLocal() as session:
            return await authorization.can_use_support_tools_db(user_id, session)


class IsCustomer(BaseFilter):
    async def __call__(
        self,
        event: Message | CallbackQuery,
        authorization: AuthorizationService,
    ) -> bool:
        user_id = _telegram_user_id(event)
        async with SessionLocal() as session:
            return not await authorization.can_use_support_tools_db(user_id, session)


def _telegram_user_id(event: Message | CallbackQuery) -> int | None:
    if event.from_user is None:
        return None
    return event.from_user.id
