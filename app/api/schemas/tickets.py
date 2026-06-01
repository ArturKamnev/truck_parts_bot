from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class TicketResponse(BaseModel):
    id: int = Field(..., description="Ticket ID")
    customer_id: int = Field(..., description="Customer user ID in database")
    status: str = Field(..., description="Ticket status (OPEN, CLAIMED, CLOSED, etc.)")
    assigned_manager_telegram_id: int | None = Field(None, description="Assigned manager Telegram ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    claimed_at: datetime | None = Field(None, description="Claim timestamp")
    closed_at: datetime | None = Field(None, description="Close timestamp")
    customer_username: str | None = Field(None, description="Telegram username of customer")
    customer_first_name: str | None = Field(None, description="Telegram first name of customer")
    customer_last_name: str | None = Field(None, description="Telegram last name of customer")


class MessageResponse(BaseModel):
    id: int = Field(..., description="Message ID")
    ticketId: int = Field(..., description="Ticket ID")
    senderType: str = Field(..., description="Sender type (customer, manager, system)")
    contentType: str = Field(..., description="Content type (text, photo, voice, video, etc.)")
    textPreview: str | None = Field(None, description="Message text preview")
    captionPreview: str | None = Field(None, description="Media caption if any")
    createdAt: datetime = Field(..., description="Creation timestamp")
    hasMedia: bool = Field(..., description="Whether message has media attachment")
    deliveryStatus: str | None = Field(None, alias="deliveryStatus", description="Delivery status of the message")
    fileName: str | None = Field(None, description="Original uploaded file name")
    mimeType: str | None = Field(None, description="Safe MIME type for the media")
    fileSize: int | None = Field(None, description="File size in bytes")
    downloadUrl: str | None = Field(None, description="Protected Mini App download URL")

    model_config = {
        "populate_by_name": True
    }


class CloseTicketRequest(BaseModel):
    as_supervisor: bool = Field(False, alias="asSupervisor")

    model_config = {
        "populate_by_name": True
    }


class MessageCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)
    as_supervisor: bool = Field(False, alias="asSupervisor")

    model_config = {
        "populate_by_name": True
    }


class CreateTicketRequest(BaseModel):
    initialMessage: str = Field(..., min_length=1, max_length=4096)


class OwnerStatsResponse(BaseModel):

    total_customers: int
    new_customers_today: int
    total_ai_messages: int
    total_tickets: int
    open_tickets: int
    claimed_tickets: int
    closed_tickets: int
    avg_first_claim_seconds: float | None


class MetricPoint(BaseModel):
    label: str
    value: int


class TrendPoint(BaseModel):
    date: str
    created: int = 0
    closed: int = 0


class ManagerPerformanceItem(BaseModel):
    telegram_user_id: int
    display_name: str
    role: str
    status: str
    active_tickets: int
    claimed_tickets: int
    closed_tickets: int


class BroadcastSummary(BaseModel):
    total: int
    delivered: int
    failed: int
    blocked: int
    recipients: int


class OwnerOverviewResponse(BaseModel):
    total_users: int
    active_users: int
    total_tickets: int
    open_tickets: int
    active_chats: int
    closed_tickets: int
    cancelled_tickets: int
    pending_chats: int
    avg_first_claim_seconds: float | None
    active_model: str | None
    ai_requests_count: int
    tickets_by_status: list[MetricPoint]
    ticket_trend: list[TrendPoint]
    manager_performance: list[ManagerPerformanceItem]
    broadcast_summary: BroadcastSummary
    language_distribution: list[MetricPoint]


class ManagerOverviewResponse(BaseModel):
    my_active_chats: int
    my_closed_chats: int
    my_claimed_chats: int
    pending_replies: int
    available_queue: int
    avg_close_seconds: float | None
    tickets_by_status: list[MetricPoint]
    ticket_trend: list[TrendPoint]


class CustomerOverviewResponse(BaseModel):
    active_ticket: TicketResponse | None
    active_chats: int
    saved_chats: int
    closed_chats: int
    broadcasts_enabled: bool
    total_tickets: int
    tickets_by_status: list[MetricPoint]


class BulkActionRequest(BaseModel):
    confirm: bool = False
    days: int = Field(14, ge=1, le=365)


class BulkActionResponse(BaseModel):
    affected_count: int
    detail: str
