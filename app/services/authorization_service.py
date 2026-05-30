from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import Settings
from app.db.models import StaffMember
from app.utils.enums import StaffRole, StaffStatus


class AuthorizationService:
    def __init__(self, settings: Settings) -> None:
        self._owner_id = settings.owner_id
        self._manager_ids = settings.manager_id_set

    def is_owner(self, telegram_user_id: int | None) -> bool:
        return telegram_user_id == self._owner_id

    def is_manager(self, telegram_user_id: int | None) -> bool:
        return telegram_user_id in self._manager_ids

    def is_co_owner(self, telegram_user_id: int | None) -> bool:
        return False

    def can_use_support_tools(self, telegram_user_id: int | None) -> bool:
        return self.is_owner(telegram_user_id) or self.is_manager(telegram_user_id)

    def detect_role(self, telegram_user_id: int | None) -> str:
        if self.is_owner(telegram_user_id):
            return "owner"
        if self.is_manager(telegram_user_id):
            return "manager"
        return "customer"

    async def is_manager_db(self, telegram_user_id: int | None, session: AsyncSession) -> bool:
        if telegram_user_id is None:
            return False

        staff_member = await self.get_staff_member_db(telegram_user_id, session)
        if staff_member is not None:
            return (
                staff_member.status == StaffStatus.ACTIVE.value
                and staff_member.role == StaffRole.MANAGER.value
            )
            
        # Fall back to settings manager ids if no DB row exists
        return telegram_user_id in self._manager_ids

    async def get_staff_member_db(
        self, telegram_user_id: int | None, session: AsyncSession
    ) -> StaffMember | None:
        if telegram_user_id is None:
            return None
        stmt = select(StaffMember).where(StaffMember.telegram_user_id == telegram_user_id)
        return await session.scalar(stmt)

    async def is_co_owner_db(self, telegram_user_id: int | None, session: AsyncSession) -> bool:
        if telegram_user_id is None or self.is_owner(telegram_user_id):
            return False
        staff_member = await self.get_staff_member_db(telegram_user_id, session)
        return (
            staff_member is not None
            and staff_member.status == StaffStatus.ACTIVE.value
            and staff_member.role == StaffRole.CO_OWNER.value
        )

    async def can_use_support_tools_db(
        self, telegram_user_id: int | None, session: AsyncSession
    ) -> bool:
        return (
            self.is_owner(telegram_user_id)
            or await self.is_co_owner_db(telegram_user_id, session)
            or await self.is_manager_db(telegram_user_id, session)
        )

    async def can_manage_staff_db(
        self, telegram_user_id: int | None, session: AsyncSession
    ) -> bool:
        return self.is_owner(telegram_user_id) or await self.is_co_owner_db(
            telegram_user_id, session
        )

    async def detect_role_db(self, telegram_user_id: int | None, session: AsyncSession) -> str:
        if self.is_owner(telegram_user_id):
            return "owner"
        if await self.is_co_owner_db(telegram_user_id, session):
            return "co_owner"
        if await self.is_manager_db(telegram_user_id, session):
            return "manager"
        return "customer"
