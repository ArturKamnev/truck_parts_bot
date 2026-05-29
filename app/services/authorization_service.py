from __future__ import annotations

from app.config import Settings


class AuthorizationService:
    def __init__(self, settings: Settings) -> None:
        self._owner_id = settings.owner_id
        self._manager_ids = settings.manager_id_set

    def is_owner(self, telegram_user_id: int | None) -> bool:
        return telegram_user_id == self._owner_id

    def is_manager(self, telegram_user_id: int | None) -> bool:
        return telegram_user_id in self._manager_ids

    def can_use_support_tools(self, telegram_user_id: int | None) -> bool:
        return self.is_owner(telegram_user_id) or self.is_manager(telegram_user_id)

    def detect_role(self, telegram_user_id: int | None) -> str:
        if self.is_owner(telegram_user_id):
            return "owner"
        if self.is_manager(telegram_user_id):
            return "manager"
        return "customer"
