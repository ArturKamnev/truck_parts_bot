from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.services.authorization_service import AuthorizationService


class IsOwner(BaseFilter):
    async def __call__(
        self,
        event: Message | CallbackQuery,
        authorization: AuthorizationService,
    ) -> bool:
        return authorization.is_owner(_telegram_user_id(event))


class IsSupport(BaseFilter):
    async def __call__(
        self,
        event: Message | CallbackQuery,
        authorization: AuthorizationService,
    ) -> bool:
        return authorization.can_use_support_tools(_telegram_user_id(event))


class IsCustomer(BaseFilter):
    async def __call__(
        self,
        event: Message | CallbackQuery,
        authorization: AuthorizationService,
    ) -> bool:
        return not authorization.can_use_support_tools(_telegram_user_id(event))


def _telegram_user_id(event: Message | CallbackQuery) -> int | None:
    if event.from_user is None:
        return None
    return event.from_user.id
