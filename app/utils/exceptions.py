from __future__ import annotations


class BotError(Exception):
    """Base domain exception."""


class AuthorizationError(BotError):
    """Raised when a Telegram user is not allowed to perform an action."""


class TicketStateError(BotError):
    """Raised when a ticket action is invalid for its current state."""


class DuplicateActiveTicketError(BotError):
    """Raised when a customer already has an active ticket."""


class UnsupportedRelayContentError(BotError):
    """Raised when a Telegram message cannot be safely relayed."""


class AIServiceError(BotError):
    """Raised for user-safe AI service failures."""


class AIServiceTimeoutError(AIServiceError):
    """Raised when the AI provider does not respond in time."""


class AIServiceRateLimitError(AIServiceError):
    """Raised when the AI provider rate-limits the request."""


class AIServiceUnavailableModelError(AIServiceError):
    """Raised when the selected AI model is unavailable."""


class AIServiceInvalidAPIKeyError(AIServiceError):
    """Raised when the AI provider rejects the configured API key."""


class AIServiceNetworkError(AIServiceError):
    """Raised when the AI provider cannot be reached."""
