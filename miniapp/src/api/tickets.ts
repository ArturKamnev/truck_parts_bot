import { API_BASE_URL, apiRequest, getStoredToken } from "./client";
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
  fileName?: string | null;
  mimeType?: string | null;
  fileSize?: number | null;
  downloadUrl?: string | null;
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

export interface MetricPoint {
  label: string;
  value: number;
}

export interface TrendPoint {
  date: string;
  created: number;
  closed: number;
}

export interface ManagerPerformanceItem {
  telegram_user_id: number;
  display_name: string;
  role: string;
  status: string;
  active_tickets: number;
  claimed_tickets: number;
  closed_tickets: number;
}

export interface BroadcastSummary {
  total: number;
  delivered: number;
  failed: number;
  blocked: number;
  recipients: number;
}

export interface OwnerOverview {
  total_users: number;
  active_users: number;
  total_tickets: number;
  open_tickets: number;
  active_chats: number;
  closed_tickets: number;
  cancelled_tickets: number;
  pending_chats: number;
  avg_first_claim_seconds: number | null;
  active_model: string | null;
  ai_requests_count: number;
  tickets_by_status: MetricPoint[];
  ticket_trend: TrendPoint[];
  manager_performance: ManagerPerformanceItem[];
  broadcast_summary: BroadcastSummary;
  language_distribution: MetricPoint[];
}

export interface ManagerOverview {
  my_active_chats: number;
  my_closed_chats: number;
  my_claimed_chats: number;
  pending_replies: number;
  available_queue: number;
  avg_close_seconds: number | null;
  tickets_by_status: MetricPoint[];
  ticket_trend: TrendPoint[];
}

export interface CustomerOverview {
  active_ticket: Ticket | null;
  active_chats: number;
  saved_chats: number;
  closed_chats: number;
  broadcasts_enabled: boolean;
  total_tickets: number;
  tickets_by_status: MetricPoint[];
}

export interface BulkActionResult {
  affected_count: number;
  detail: string;
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

const normalizeMetricPoints = (points: MetricPoint[] | undefined | null): MetricPoint[] =>
  (points || []).map((point) => ({
    label: String(point?.label || "unknown"),
    value: Number(point?.value) || 0,
  }));

const normalizeTrendPoints = (points: TrendPoint[] | undefined | null): TrendPoint[] =>
  (points || []).map((point) => ({
    date: String(point?.date || ""),
    created: Number(point?.created) || 0,
    closed: Number(point?.closed) || 0,
  }));

export const getOwnerOverview = async (): Promise<OwnerOverview> => {
  const overview = await apiRequest<OwnerOverview>("/api/owner/overview");
  return {
    total_users: Number(overview?.total_users) || 0,
    active_users: Number(overview?.active_users) || 0,
    total_tickets: Number(overview?.total_tickets) || 0,
    open_tickets: Number(overview?.open_tickets) || 0,
    active_chats: Number(overview?.active_chats) || 0,
    closed_tickets: Number(overview?.closed_tickets) || 0,
    cancelled_tickets: Number(overview?.cancelled_tickets) || 0,
    pending_chats: Number(overview?.pending_chats) || 0,
    avg_first_claim_seconds: overview?.avg_first_claim_seconds !== undefined && overview?.avg_first_claim_seconds !== null ? Number(overview.avg_first_claim_seconds) : null,
    active_model: overview?.active_model || null,
    ai_requests_count: Number(overview?.ai_requests_count) || 0,
    tickets_by_status: normalizeMetricPoints(overview?.tickets_by_status),
    ticket_trend: normalizeTrendPoints(overview?.ticket_trend),
    manager_performance: (overview?.manager_performance || []).map((item) => ({
      telegram_user_id: Number(item?.telegram_user_id) || 0,
      display_name: String(item?.display_name || item?.telegram_user_id || ""),
      role: String(item?.role || "manager"),
      status: String(item?.status || "active"),
      active_tickets: Number(item?.active_tickets) || 0,
      claimed_tickets: Number(item?.claimed_tickets) || 0,
      closed_tickets: Number(item?.closed_tickets) || 0,
    })),
    broadcast_summary: {
      total: Number(overview?.broadcast_summary?.total) || 0,
      delivered: Number(overview?.broadcast_summary?.delivered) || 0,
      failed: Number(overview?.broadcast_summary?.failed) || 0,
      blocked: Number(overview?.broadcast_summary?.blocked) || 0,
      recipients: Number(overview?.broadcast_summary?.recipients) || 0,
    },
    language_distribution: normalizeMetricPoints(overview?.language_distribution),
  };
};

export const getManagerOverview = async (): Promise<ManagerOverview> => {
  const overview = await apiRequest<ManagerOverview>("/api/manager/overview");
  return {
    my_active_chats: Number(overview?.my_active_chats) || 0,
    my_closed_chats: Number(overview?.my_closed_chats) || 0,
    my_claimed_chats: Number(overview?.my_claimed_chats) || 0,
    pending_replies: Number(overview?.pending_replies) || 0,
    available_queue: Number(overview?.available_queue) || 0,
    avg_close_seconds: overview?.avg_close_seconds !== undefined && overview?.avg_close_seconds !== null ? Number(overview.avg_close_seconds) : null,
    tickets_by_status: normalizeMetricPoints(overview?.tickets_by_status),
    ticket_trend: normalizeTrendPoints(overview?.ticket_trend),
  };
};

export const getCustomerOverview = async (): Promise<CustomerOverview> => {
  const overview = await apiRequest<CustomerOverview>("/api/customer/overview");
  return {
    active_ticket: overview?.active_ticket ? normalizeTicket(overview.active_ticket) : null,
    active_chats: Number(overview?.active_chats) || 0,
    saved_chats: Number(overview?.saved_chats) || 0,
    closed_chats: Number(overview?.closed_chats) || 0,
    broadcasts_enabled: Boolean(overview?.broadcasts_enabled),
    total_tickets: Number(overview?.total_tickets) || 0,
    tickets_by_status: normalizeMetricPoints(overview?.tickets_by_status),
  };
};

const ownerBulkAction = async (path: string, days?: number): Promise<BulkActionResult> => {
  const result = await apiRequest<BulkActionResult>(path, {
    method: "POST",
    body: JSON.stringify({ confirm: true, days }),
  });
  return {
    affected_count: Number(result?.affected_count) || 0,
    detail: String(result?.detail || ""),
  };
};

export const clearClosedTicketsFromView = (): Promise<BulkActionResult> =>
  ownerBulkAction("/api/owner/tickets/clear-closed");

export const clearCancelledTicketsFromView = (): Promise<BulkActionResult> =>
  ownerBulkAction("/api/owner/tickets/clear-cancelled");

export const closeStaleOpenTickets = (days = 14): Promise<BulkActionResult> =>
  ownerBulkAction("/api/owner/tickets/close-stale", days);

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

const uploadTicketFile = async (
  path: string,
  file: File,
  caption?: string,
  asSupervisor?: boolean
): Promise<TicketMessage> => {
  const formData = new FormData();
  formData.append("file", file);
  if (caption?.trim()) {
    formData.append("caption", caption.trim());
  }
  if (typeof asSupervisor === "boolean") {
    formData.append("asSupervisor", String(asSupervisor));
  }

  const token = getStoredToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
  });
  if (!response.ok) {
    let message = response.statusText || "Upload failed";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      // ignore
    }
    throw { status: response.status, message };
  }
  return normalizeTicketMessage(await response.json());
};

export const uploadCustomerTicketFile = async (
  ticketId: number,
  file: File,
  caption?: string
): Promise<TicketMessage> => {
  return uploadTicketFile(`/api/customer/tickets/${ticketId}/messages/upload`, file, caption);
};

export const uploadManagerTicketFile = async (
  ticketId: number,
  file: File,
  caption?: string,
  asSupervisor: boolean = false
): Promise<TicketMessage> => {
  return uploadTicketFile(
    `/api/manager/tickets/${ticketId}/messages/upload`,
    file,
    caption,
    asSupervisor
  );
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
  file_name?: string | null;
  mime_type?: string | null;
  file_size?: number | null;
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

export const setBroadcastAttachment = async (
  broadcastId: number,
  file: File,
  caption?: string
): Promise<Broadcast> => {
  const formData = new FormData();
  formData.append("file", file);
  if (caption?.trim()) formData.append("caption", caption.trim());
  const token = getStoredToken();
  const response = await fetch(`${API_BASE_URL}/api/owner/broadcasts/${broadcastId}/attachment`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
  });
  if (!response.ok) {
    let message = response.statusText || "Upload failed";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      // ignore
    }
    throw { status: response.status, message };
  }
  return normalizeBroadcast(await response.json());
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
