from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AVAILABLE_MODELS, Settings
from app.db.models import AppSetting, AuditEvent
from app.services.authorization_service import AuthorizationService
from app.utils.exceptions import AuthorizationError, TicketStateError

ACTIVE_MODEL_KEY = "active_model"


class SettingsService:
    def __init__(self, settings: Settings, authorization: AuthorizationService) -> None:
        self._settings = settings
        self._authorization = authorization

    async def get_active_model(self, session: AsyncSession) -> str:
        setting = await session.get(AppSetting, ACTIVE_MODEL_KEY)
        if setting and setting.value in AVAILABLE_MODELS:
            return setting.value
        return self._settings.default_model

    async def ensure_defaults(self, session: AsyncSession) -> None:
        setting = await session.get(AppSetting, ACTIVE_MODEL_KEY)
        if setting is None:
            session.add(
                AppSetting(
                    key=ACTIVE_MODEL_KEY,
                    value=self._settings.default_model,
                    updated_by_telegram_id=None,
                )
            )
            await session.flush()

    async def switch_active_model(
        self, session: AsyncSession, *, actor_telegram_id: int, model_id: str
    ) -> str:
        if not self._authorization.is_owner(actor_telegram_id):
            raise AuthorizationError("Only owner can switch AI model")
        if model_id not in AVAILABLE_MODELS:
            raise TicketStateError("Unknown model id")

        setting = await session.get(AppSetting, ACTIVE_MODEL_KEY)
        if setting is None:
            setting = AppSetting(key=ACTIVE_MODEL_KEY, value=model_id)
            session.add(setting)
        else:
            setting.value = model_id

        setting.updated_by_telegram_id = actor_telegram_id
        setting.updated_at = datetime.now(UTC)
        session.add(
            AuditEvent(
                event_type="ai_model_switched",
                actor_telegram_id=actor_telegram_id,
                metadata_json={"model_id": model_id},
            )
        )
        await session.flush()
        return model_id

    async def list_settings(self, session: AsyncSession) -> dict[str, str]:
        rows = await session.scalars(select(AppSetting))
        return {row.key: row.value for row in rows}
