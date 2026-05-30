from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ErrorEvent

from app.config import Settings
from app.handlers import callbacks, customer, manager, owner
from app.services.ai_service import AIService
from app.services.ai_streaming_lock import AIStreamingLockRegistry
from app.services.authorization_service import AuthorizationService
from app.services.broadcast_service import BroadcastService
from app.services.knowledge_service import KnowledgeService
from app.services.relay_service import RelayService
from app.services.settings_service import SettingsService
from app.services.statistics_service import StatisticsService
from app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)


def create_bot_and_dispatcher(settings: Settings) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    authorization = AuthorizationService(settings)
    settings_service = SettingsService(settings, authorization)
    knowledge_service = KnowledgeService()
    ai_service = AIService(settings, settings_service, knowledge_service)
    streaming_locks = AIStreamingLockRegistry()
    ticket_service = TicketService(authorization)
    relay_service = RelayService(settings, ticket_service, ai_service)
    broadcast_service = BroadcastService(settings, authorization, relay_service)
    statistics_service = StatisticsService()

    dp["settings"] = settings
    dp["authorization"] = authorization
    dp["settings_service"] = settings_service
    dp["knowledge_service"] = knowledge_service
    dp["ai_service"] = ai_service
    dp["streaming_locks"] = streaming_locks
    dp["ticket_service"] = ticket_service
    dp["relay_service"] = relay_service
    dp["broadcast_service"] = broadcast_service
    dp["statistics_service"] = statistics_service

    dp.include_router(owner.router)
    dp.include_router(callbacks.router)
    dp.include_router(manager.router)
    dp.include_router(customer.router)
    dp.errors.register(error_handler)
    return bot, dp


async def error_handler(event: ErrorEvent) -> bool:
    exception = event.exception
    if isinstance(exception, TelegramAPIError):
        logger.warning("Telegram API error: %s", exception)
    else:
        logger.exception("Unhandled update error", exc_info=exception)
    return True
