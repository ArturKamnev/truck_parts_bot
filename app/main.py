from __future__ import annotations

import asyncio
import logging

from pydantic import ValidationError

from app.config import get_settings
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    try:
        settings = get_settings()
    except ValidationError as exc:
        logging.basicConfig(level=logging.ERROR, format="%(levelname)s [%(name)s] %(message)s")
        logging.getLogger(__name__).error("Invalid environment configuration: %s", exc)
        raise SystemExit(1) from exc

    setup_logging(settings.log_level)
    from app.bot import create_bot_and_dispatcher
    from app.db.session import SessionLocal, engine
    from app.services.authorization_service import AuthorizationService
    from app.services.settings_service import SettingsService

    bot, dp = create_bot_and_dispatcher(settings)

    async with SessionLocal() as session, session.begin():
        await SettingsService(settings, AuthorizationService(settings)).ensure_defaults(session)

    logger.info("Starting Telegram bot long polling")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
