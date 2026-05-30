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

