import { apiRequest } from "./client";

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
  return apiRequest<Ticket[]>("/api/customer/tickets");
};

export const getCustomerTicketDetails = async (ticketId: number): Promise<Ticket> => {
  return apiRequest<Ticket>(`/api/customer/tickets/${ticketId}`);
};

export const getCustomerTicketMessages = async (
  ticketId: number,
  limit: number = 50,
  afterId?: number
): Promise<TicketMessage[]> => {
  const query = `limit=${limit}` + (afterId !== undefined ? `&after_id=${afterId}` : "");
  return apiRequest<TicketMessage[]>(`/api/customer/tickets/${ticketId}/messages?${query}`);
};

// --- Manager API ---
export const getManagerNewTickets = async (): Promise<Ticket[]> => {
  return apiRequest<Ticket[]>("/api/manager/tickets/new");
};

export const getManagerActiveTickets = async (): Promise<Ticket[]> => {
  return apiRequest<Ticket[]>("/api/manager/tickets/active");
};

export const getManagerTicketDetails = async (ticketId: number): Promise<Ticket> => {
  return apiRequest<Ticket>(`/api/manager/tickets/${ticketId}`);
};

export const getManagerTicketMessages = async (
  ticketId: number,
  limit: number = 50,
  afterId?: number
): Promise<TicketMessage[]> => {
  const query = `limit=${limit}` + (afterId !== undefined ? `&after_id=${afterId}` : "");
  return apiRequest<TicketMessage[]>(`/api/manager/tickets/${ticketId}/messages?${query}`);
};

// --- Owner API ---
export const getOwnerTickets = async (): Promise<Ticket[]> => {
  return apiRequest<Ticket[]>("/api/owner/tickets");
};

export const getOwnerStats = async (): Promise<OwnerStats> => {
  return apiRequest<OwnerStats>("/api/owner/stats");
};

// --- Interactive Manager / Owner Actions ---
export const claimTicket = async (ticketId: number): Promise<Ticket> => {
  return apiRequest<Ticket>(`/api/manager/tickets/${ticketId}/claim`, {
    method: "POST",
  });
};

export const closeTicket = async (ticketId: number, asSupervisor: boolean = false): Promise<Ticket> => {
  return apiRequest<Ticket>(`/api/manager/tickets/${ticketId}/close`, {
    method: "POST",
    body: JSON.stringify({ asSupervisor }),
  });
};

export const sendTicketMessage = async (
  ticketId: number,
  text: string,
  asSupervisor: boolean = false
): Promise<TicketMessage> => {
  return apiRequest<TicketMessage>(`/api/manager/tickets/${ticketId}/messages`, {
    method: "POST",
    body: JSON.stringify({ text, asSupervisor }),
  });
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
  return apiRequest<StaffMember[]>("/api/owner/managers");
};

export const getOwnerUsers = async (): Promise<BotUser[]> => {
  return apiRequest<BotUser[]>("/api/owner/users");
};

export const promoteManager = async (telegramUserId: number, notes?: string): Promise<StaffMember> => {
  return apiRequest<StaffMember>(`/api/owner/managers/${telegramUserId}/promote`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
};

export const disableManager = async (telegramUserId: number): Promise<StaffMember> => {
  return apiRequest<StaffMember>(`/api/owner/managers/${telegramUserId}/disable`, {
    method: "POST",
  });
};

export const promoteCoOwner = async (telegramUserId: number, notes?: string): Promise<StaffMember> => {
  return apiRequest<StaffMember>(`/api/owner/co-owners/${telegramUserId}/promote`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
};

export const disableCoOwner = async (telegramUserId: number): Promise<StaffMember> => {
  return apiRequest<StaffMember>(`/api/owner/co-owners/${telegramUserId}/disable`, {
    method: "POST",
  });
};

export const getManagerStats = async (telegramUserId: number): Promise<ManagerStats> => {
  return apiRequest<ManagerStats>(`/api/owner/managers/${telegramUserId}/stats`);
};

// --- CRM Expansion & AI Endpoints ---
export const createCustomerTicket = async (initialMessage: string): Promise<Ticket> => {
  return apiRequest<Ticket>("/api/customer/tickets", {
    method: "POST",
    body: JSON.stringify({ initialMessage }),
  });
};

export const sendCustomerMessage = async (ticketId: number, text: string): Promise<TicketMessage> => {
  return apiRequest<TicketMessage>(`/api/customer/tickets/${ticketId}/messages`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
};

export const getManagerClosedTickets = async (): Promise<Ticket[]> => {
  return apiRequest<Ticket[]>("/api/manager/tickets/closed");
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
  return apiRequest<AIMessage[]>("/api/ai/history");
};

export interface Broadcast {
  id: number;
  created_by_telegram_id: number;
  status: string;
  content_preview: string | null;
  recipient_count: number;
  delivered_count: number;
  failed_count: number;
  blocked_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
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
  return apiRequest<{ tickets_claimed: number; tickets_closed: number }>("/api/manager/stats");
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
  return apiRequest<Broadcast[]>("/api/owner/broadcasts");
};



