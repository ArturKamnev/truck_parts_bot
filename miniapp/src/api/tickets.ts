import { apiRequest } from "./client";
import {
  normalizeTicket,
  normalizeTicketMessage,
  normalizeStaffMember,
  normalizeBroadcast,
  normalizeAIMessage,
} from "../utils/normalization";

export interface Ticket {
  id: number;
  customer_id: number;
  status: "OPEN" | "CLAIMED" | "CLOSED" | string;
  assigned_manager_telegram_id: number | null;
  created_at: string;
  claimed_at: string | null;
  closed_at: string | null;
  customer_username: string | null;
  customer_first_name: string | null;
  customer_last_name: string | null;
}

export interface TicketMessage {
  id: number;
  ticketId: number;
  senderType: "customer" | "manager" | "system" | string;
  contentType: "text" | "photo" | "voice" | "video" | string;
  textPreview: string | null;
  captionPreview: string | null;
  createdAt: string;
  hasMedia: boolean;
  deliveryStatus?: string | null;
}

export interface OwnerStats {
  total_customers: number;
  new_customers_today: number;
  total_ai_messages: number;
  total_tickets: number;
  open_tickets: number;
  claimed_tickets: number;
  closed_tickets: number;
  avg_first_claim_seconds: number | null;
}

// --- Customer API ---
export const getCustomerTickets = async (): Promise<Ticket[]> => {
  const tickets = await apiRequest<Ticket[]>("/api/customer/tickets");
  return (tickets || []).map(normalizeTicket);
};

export const getCustomerTicketDetails = async (ticketId: number): Promise<Ticket> => {
  const ticket = await apiRequest<Ticket>(`/api/customer/tickets/${ticketId}`);
  return normalizeTicket(ticket);
};

export const getCustomerTicketMessages = async (
  ticketId: number,
  limit: number = 50,
  afterId?: number
): Promise<TicketMessage[]> => {
  const query = `limit=${limit}` + (afterId !== undefined ? `&after_id=${afterId}` : "");
  const messages = await apiRequest<TicketMessage[]>(`/api/customer/tickets/${ticketId}/messages?${query}`);
  return (messages || []).map(normalizeTicketMessage);
};

// --- Manager API ---
export const getManagerNewTickets = async (): Promise<Ticket[]> => {
  const tickets = await apiRequest<Ticket[]>("/api/manager/tickets/new");
  return (tickets || []).map(normalizeTicket);
};

export const getManagerActiveTickets = async (): Promise<Ticket[]> => {
  const tickets = await apiRequest<Ticket[]>("/api/manager/tickets/active");
  return (tickets || []).map(normalizeTicket);
};

export const getManagerTicketDetails = async (ticketId: number): Promise<Ticket> => {
  const ticket = await apiRequest<Ticket>(`/api/manager/tickets/${ticketId}`);
  return normalizeTicket(ticket);
};

export const getManagerTicketMessages = async (
  ticketId: number,
  limit: number = 50,
  afterId?: number
): Promise<TicketMessage[]> => {
  const query = `limit=${limit}` + (afterId !== undefined ? `&after_id=${afterId}` : "");
  const messages = await apiRequest<TicketMessage[]>(`/api/manager/tickets/${ticketId}/messages?${query}`);
  return (messages || []).map(normalizeTicketMessage);
};

// --- Owner API ---
export const getOwnerTickets = async (): Promise<Ticket[]> => {
  const tickets = await apiRequest<Ticket[]>("/api/owner/tickets");
  return (tickets || []).map(normalizeTicket);
};

export const getOwnerStats = async (): Promise<OwnerStats> => {
  const stats = await apiRequest<OwnerStats>("/api/owner/stats");
  return {
    total_customers: Number(stats?.total_customers) || 0,
    new_customers_today: Number(stats?.new_customers_today) || 0,
    total_ai_messages: Number(stats?.total_ai_messages) || 0,
    total_tickets: Number(stats?.total_tickets) || 0,
    open_tickets: Number(stats?.open_tickets) || 0,
    claimed_tickets: Number(stats?.claimed_tickets) || 0,
    closed_tickets: Number(stats?.closed_tickets) || 0,
    avg_first_claim_seconds: stats?.avg_first_claim_seconds !== undefined && stats?.avg_first_claim_seconds !== null ? Number(stats.avg_first_claim_seconds) : null,
  };
};

// --- Interactive Manager / Owner Actions ---
export const claimTicket = async (ticketId: number): Promise<Ticket> => {
  const ticket = await apiRequest<Ticket>(`/api/manager/tickets/${ticketId}/claim`, {
    method: "POST",
  });
  return normalizeTicket(ticket);
};

export const closeTicket = async (ticketId: number, asSupervisor: boolean = false): Promise<Ticket> => {
  const ticket = await apiRequest<Ticket>(`/api/manager/tickets/${ticketId}/close`, {
    method: "POST",
    body: JSON.stringify({ asSupervisor }),
  });
  return normalizeTicket(ticket);
};

export const sendTicketMessage = async (
  ticketId: number,
  text: string,
  asSupervisor: boolean = false
): Promise<TicketMessage> => {
  const message = await apiRequest<TicketMessage>(`/api/manager/tickets/${ticketId}/messages`, {
    method: "POST",
    body: JSON.stringify({ text, asSupervisor }),
  });
  return normalizeTicketMessage(message);
};

export interface StaffMember {
  id: number;
  telegram_user_id: number;
  role: string;
  status: "active" | "disabled" | string;
  added_by_telegram_id: number | null;
  added_at: string;
  disabled_at: string | null;
  notes: string | null;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  display_name: string | null;
}

export interface BotUser {
  id: number;
  telegram_user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
}

export interface ManagerStats {
  telegram_user_id: number;
  tickets_claimed: number;
  tickets_closed: number;
}

export const getOwnerManagers = async (): Promise<StaffMember[]> => {
  const managers = await apiRequest<StaffMember[]>("/api/owner/managers");
  return (managers || []).map(normalizeStaffMember);
};

export const getOwnerUsers = async (): Promise<BotUser[]> => {
  const users = await apiRequest<BotUser[]>("/api/owner/users");
  return (users || []).map((u) => ({
    id: Number(u?.id) || 0,
    telegram_user_id: Number(u?.telegram_user_id) || 0,
    username: typeof u?.username === "string" ? u.username : null,
    first_name: typeof u?.first_name === "string" ? u.first_name : null,
    last_name: typeof u?.last_name === "string" ? u.last_name : null,
  }));
};

export const promoteManager = async (telegramUserId: number, notes?: string): Promise<StaffMember> => {
  const manager = await apiRequest<StaffMember>(`/api/owner/managers/${telegramUserId}/promote`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
  return normalizeStaffMember(manager);
};

export const disableManager = async (telegramUserId: number): Promise<StaffMember> => {
  const manager = await apiRequest<StaffMember>(`/api/owner/managers/${telegramUserId}/disable`, {
    method: "POST",
  });
  return normalizeStaffMember(manager);
};

export const promoteCoOwner = async (telegramUserId: number, notes?: string): Promise<StaffMember> => {
  const coOwner = await apiRequest<StaffMember>(`/api/owner/co-owners/${telegramUserId}/promote`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
  return normalizeStaffMember(coOwner);
};

export const disableCoOwner = async (telegramUserId: number): Promise<StaffMember> => {
  const coOwner = await apiRequest<StaffMember>(`/api/owner/co-owners/${telegramUserId}/disable`, {
    method: "POST",
  });
  return normalizeStaffMember(coOwner);
};

export const getManagerStats = async (telegramUserId: number): Promise<ManagerStats> => {
  const stats = await apiRequest<ManagerStats>(`/api/owner/managers/${telegramUserId}/stats`);
  return {
    telegram_user_id: Number(stats?.telegram_user_id) || 0,
    tickets_claimed: Number(stats?.tickets_claimed) || 0,
    tickets_closed: Number(stats?.tickets_closed) || 0,
  };
};

// --- CRM Expansion & AI Endpoints ---
export const createCustomerTicket = async (initialMessage: string): Promise<Ticket> => {
  const ticket = await apiRequest<Ticket>("/api/customer/tickets", {
    method: "POST",
    body: JSON.stringify({ initialMessage }),
  });
  return normalizeTicket(ticket);
};

export const sendCustomerMessage = async (ticketId: number, text: string): Promise<TicketMessage> => {
  const message = await apiRequest<TicketMessage>(`/api/customer/tickets/${ticketId}/messages`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
  return normalizeTicketMessage(message);
};

export const getManagerClosedTickets = async (): Promise<Ticket[]> => {
  const tickets = await apiRequest<Ticket[]>("/api/manager/tickets/closed");
  return (tickets || []).map(normalizeTicket);
};

export interface AIMessage {
  id: number;
  role: string;
  content: string;
  model_id: string | null;
  created_at: string;
}

export const sendAIChatMessage = async (message: string): Promise<{ response: string; model_id: string }> => {
  return apiRequest<{ response: string; model_id: string }>("/api/ai/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
};

export const getAIChatHistory = async (): Promise<AIMessage[]> => {
  const history = await apiRequest<AIMessage[]>("/api/ai/history");
  return (history || []).map(normalizeAIMessage);
};

export interface Broadcast {
  id: number;
  created_by_telegram_id: number;
  status: string;
  content_type?: string | null;
  content_preview: string | null;
  button_selection?: string;
  recipient_count: number;
  delivered_count: number;
  failed_count: number;
  blocked_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface BroadcastPreview extends Broadcast {
  eligible_recipient_count: number;
  available_buttons: Record<string, boolean>;
}

export interface ActiveModelInfo {
  active_model: string;
  available_models: Record<string, string>;
}

export const toggleBroadcastSettings = async (enabled: boolean): Promise<boolean> => {
  return apiRequest<boolean>("/api/customer/profile/broadcast-toggle", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
};

export const getManagerPersonalStats = async (): Promise<{ tickets_claimed: number; tickets_closed: number }> => {
  const stats = await apiRequest<{ tickets_claimed: number; tickets_closed: number }>("/api/manager/stats");
  return {
    tickets_claimed: Number(stats?.tickets_claimed) || 0,
    tickets_closed: Number(stats?.tickets_closed) || 0,
  };
};

export const getActiveModel = async (): Promise<ActiveModelInfo> => {
  return apiRequest<ActiveModelInfo>("/api/owner/settings/active-model");
};

export const switchActiveModel = async (modelId: string): Promise<string> => {
  return apiRequest<string>("/api/owner/settings/active-model", {
    method: "POST",
    body: JSON.stringify({ model_id: modelId }),
  });
};

export const getOwnerBroadcasts = async (): Promise<Broadcast[]> => {
  const broadcasts = await apiRequest<Broadcast[]>("/api/owner/broadcasts");
  return (broadcasts || []).map(normalizeBroadcast);
};

export const createBroadcastDraft = async (): Promise<Broadcast> => {
  const broadcast = await apiRequest<Broadcast>("/api/owner/broadcasts/drafts", {
    method: "POST",
  });
  return normalizeBroadcast(broadcast);
};

export const setBroadcastContent = async (broadcastId: number, text: string): Promise<Broadcast> => {
  const broadcast = await apiRequest<Broadcast>(`/api/owner/broadcasts/${broadcastId}/content`, {
    method: "PUT",
    body: JSON.stringify({ text }),
  });
  return normalizeBroadcast(broadcast);
};

export const setBroadcastButtons = async (broadcastId: number, selection: string): Promise<Broadcast> => {
  const broadcast = await apiRequest<Broadcast>(`/api/owner/broadcasts/${broadcastId}/buttons`, {
    method: "PUT",
    body: JSON.stringify({ selection }),
  });
  return normalizeBroadcast(broadcast);
};

export const previewBroadcast = async (broadcastId: number): Promise<BroadcastPreview> => {
  const preview = await apiRequest<BroadcastPreview>(`/api/owner/broadcasts/${broadcastId}/preview`);
  return {
    ...normalizeBroadcast(preview),
    eligible_recipient_count: Number(preview?.eligible_recipient_count) || 0,
    available_buttons: preview?.available_buttons && typeof preview.available_buttons === "object"
      ? preview.available_buttons
      : {},
  };
};

export const sendBroadcast = async (broadcastId: number): Promise<Broadcast> => {
  const broadcast = await apiRequest<Broadcast>(`/api/owner/broadcasts/${broadcastId}/send`, {
    method: "POST",
  });
  return normalizeBroadcast(broadcast);
};

export const cancelBroadcast = async (broadcastId: number): Promise<Broadcast> => {
  const broadcast = await apiRequest<Broadcast>(`/api/owner/broadcasts/${broadcastId}/cancel`, {
    method: "POST",
  });
  return normalizeBroadcast(broadcast);
};



