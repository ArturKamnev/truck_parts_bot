from __future__ import annotations

import pytest

from app.config import AVAILABLE_MODELS
from app.db.models import AppSetting
from app.services.settings_service import ACTIVE_MODEL_KEY, SettingsService
from app.utils.exceptions import TicketStateError


async def test_switch_model_only_seeded_values(session, settings_service: SettingsService) -> None:
    with pytest.raises(TicketStateError):
        await settings_service.switch_active_model(
            session,
            actor_telegram_id=999,
            model_id="arbitrary/model",
        )


async def test_active_model_persistence(session, settings_service: SettingsService) -> None:
    model_id = list(AVAILABLE_MODELS.keys())[1]
    await settings_service.switch_active_model(
        session,
        actor_telegram_id=999,
        model_id=model_id,
    )
    await session.commit()

    persisted = await session.get(AppSetting, ACTIVE_MODEL_KEY)
    assert persisted is not None
    assert persisted.value == model_id
    assert await settings_service.get_active_model(session) == model_id
