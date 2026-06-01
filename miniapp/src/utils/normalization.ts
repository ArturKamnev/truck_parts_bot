import { type UserProfile } from "../api/auth";
import { type Ticket, type TicketMessage, type StaffMember, type Broadcast, type AIMessage } from "../api/tickets";

// --- Safe string & string method helpers ---

export function safeText(value: unknown, fallback = "—"): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export function safeUpperCase(value: unknown, fallback = ""): string {
  if (value === null || value === undefined) return fallback;
  const text = typeof value === "string" ? value : String(value);
  return text.toUpperCase() || fallback;
}

export function safeLowerCase(value: unknown, fallback = ""): string {
  if (value === null || value === undefined) return fallback;
  const text = typeof value === "string" ? value : String(value);
  return text.toLowerCase() || fallback;
}

export function safeSlice(value: unknown, start: number, end?: number, fallback = ""): string {
  if (typeof value !== "string") {
    return fallback;
  }
  return value.slice(start, end);
}

export function getInitials(displayName: unknown, fallback = "U"): string {
  if (!displayName || typeof displayName !== "string") {
    return fallback;
  }
  const clean = displayName.trim();
  if (!clean) return fallback;
  return clean.charAt(0).toUpperCase() || fallback;
}

// --- Safe Date/Time helpers ---

export function safeTime(dateInput: unknown, fallback = "—"): string {
  if (!dateInput) return fallback;
  const d = new Date(dateInput as any);
  if (isNaN(d.getTime())) return fallback;
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function safeDate(dateInput: unknown, fallback = "—"): string {
  if (!dateInput) return fallback;
  const d = new Date(dateInput as any);
  if (isNaN(d.getTime())) return fallback;
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// --- Normalization calculations ---

export function computeDisplayName(
  displayName: unknown,
  username: unknown,
  firstName: unknown,
  lastName: unknown,
  telegramUserId: unknown
): string {
  const dpStr = typeof displayName === "string" ? displayName.trim() : "";
  if (dpStr) return dpStr;

  const uStr = typeof username === "string" ? username.trim() : "";
  if (uStr) return uStr;

  const fStr = typeof firstName === "string" ? firstName.trim() : "";
  const lStr = typeof lastName === "string" ? lastName.trim() : "";
  const joined = [fStr, lStr].filter(Boolean).join(" ");
  if (joined) return joined;

  if (telegramUserId !== undefined && telegramUserId !== null) {
    const idStr = String(telegramUserId).trim();
    if (idStr) return `User ${idStr}`;
  }

  return "User";
}

// --- Boundary Normalizers ---

export function normalizeUserProfile(profile: any): UserProfile {
  if (!profile) {
    return {
      telegram_user_id: 0,
      role: "unsupportedRole" as any,
      username: null,
      first_name: null,
      last_name: null,
      display_name: "User",
      broadcasts_enabled: false,
      miniapp_url: null,
      selected_ticket_id: null,
      feature_flags: {},
      preferred_language: "ru",
    };
  }

  const role = ["customer", "manager", "owner", "co_owner"].includes(profile.role)
    ? profile.role
    : "unsupportedRole";

  const preferred_language = ["ru", "en", "ky"].includes(profile.preferred_language)
    ? profile.preferred_language
    : "ru";

  const display_name = computeDisplayName(
    profile.display_name,
    profile.username,
    profile.first_name,
    profile.last_name,
    profile.telegram_user_id
  );

  return {
    telegram_user_id: Number(profile.telegram_user_id) || 0,
    role: role as any,
    username: typeof profile.username === "string" ? profile.username : null,
    first_name: typeof profile.first_name === "string" ? profile.first_name : null,
    last_name: typeof profile.last_name === "string" ? profile.last_name : null,
    display_name,
    broadcasts_enabled: Boolean(profile.broadcasts_enabled),
    miniapp_url: typeof profile.miniapp_url === "string" ? profile.miniapp_url : null,
    customer_mode: typeof profile.customer_mode === "string" ? profile.customer_mode : undefined,
    selected_ticket_id: profile.selected_ticket_id !== undefined && profile.selected_ticket_id !== null ? Number(profile.selected_ticket_id) : null,
    feature_flags: profile.feature_flags && typeof profile.feature_flags === "object" ? profile.feature_flags : {},
    preferred_language,
  };
}

export function normalizeTicket(ticket: any): Ticket {
  if (!ticket) {
    return {
      id: 0,
      customer_id: 0,
      status: "UNKNOWN",
      assigned_manager_telegram_id: null,
      created_at: new Date().toISOString(),
      claimed_at: null,
      closed_at: null,
      customer_username: null,
      customer_first_name: null,
      customer_last_name: null,
    };
  }

  return {
    id: Number(ticket.id) || 0,
    customer_id: Number(ticket.customer_id) || 0,
    status: typeof ticket.status === "string" ? ticket.status : "UNKNOWN",
    assigned_manager_telegram_id: ticket.assigned_manager_telegram_id ? Number(ticket.assigned_manager_telegram_id) : null,
    created_at: typeof ticket.created_at === "string" ? ticket.created_at : new Date().toISOString(),
    claimed_at: typeof ticket.claimed_at === "string" ? ticket.claimed_at : null,
    closed_at: typeof ticket.closed_at === "string" ? ticket.closed_at : null,
    customer_username: typeof ticket.customer_username === "string" ? ticket.customer_username : null,
    customer_first_name: typeof ticket.customer_first_name === "string" ? ticket.customer_first_name : null,
    customer_last_name: typeof ticket.customer_last_name === "string" ? ticket.customer_last_name : null,
  };
}

export function normalizeTicketMessage(msg: any): TicketMessage {
  if (!msg) {
    return {
      id: 0,
      ticketId: 0,
      senderType: "UNKNOWN",
      contentType: "text",
      textPreview: null,
      captionPreview: null,
      createdAt: new Date().toISOString(),
      hasMedia: false,
      fileName: null,
      mimeType: null,
      fileSize: null,
      downloadUrl: null,
    };
  }

  return {
    id: Number(msg.id) || 0,
    ticketId: Number(msg.ticketId) || 0,
    senderType: typeof msg.senderType === "string" ? msg.senderType : "UNKNOWN",
    contentType: typeof msg.contentType === "string" ? msg.contentType : "text",
    textPreview: typeof msg.textPreview === "string" ? msg.textPreview : null,
    captionPreview: typeof msg.captionPreview === "string" ? msg.captionPreview : null,
    createdAt: typeof msg.createdAt === "string" ? msg.createdAt : new Date().toISOString(),
    hasMedia: Boolean(msg.hasMedia),
    deliveryStatus: typeof msg.deliveryStatus === "string" ? msg.deliveryStatus : null,
    fileName: typeof msg.fileName === "string" ? msg.fileName : null,
    mimeType: typeof msg.mimeType === "string" ? msg.mimeType : null,
    fileSize: msg.fileSize !== undefined && msg.fileSize !== null ? Number(msg.fileSize) : null,
    downloadUrl: typeof msg.downloadUrl === "string" ? msg.downloadUrl : null,
  };
}

export function normalizeStaffMember(staff: any): StaffMember {
  if (!staff) {
    return {
      id: 0,
      telegram_user_id: 0,
      role: "unsupportedRole",
      status: "UNKNOWN",
      added_by_telegram_id: null,
      added_at: new Date().toISOString(),
      disabled_at: null,
      notes: null,
      username: null,
      first_name: null,
      last_name: null,
      display_name: "User",
    };
  }

  const display_name = computeDisplayName(
    staff.display_name,
    staff.username,
    staff.first_name,
    staff.last_name,
    staff.telegram_user_id
  );

  return {
    id: Number(staff.id) || 0,
    telegram_user_id: Number(staff.telegram_user_id) || 0,
    role: typeof staff.role === "string" ? staff.role : "unsupportedRole",
    status: typeof staff.status === "string" ? staff.status : "UNKNOWN",
    added_by_telegram_id: staff.added_by_telegram_id ? Number(staff.added_by_telegram_id) : null,
    added_at: typeof staff.added_at === "string" ? staff.added_at : new Date().toISOString(),
    disabled_at: typeof staff.disabled_at === "string" ? staff.disabled_at : null,
    notes: typeof staff.notes === "string" ? staff.notes : null,
    username: typeof staff.username === "string" ? staff.username : null,
    first_name: typeof staff.first_name === "string" ? staff.first_name : null,
    last_name: typeof staff.last_name === "string" ? staff.last_name : null,
    display_name,
  };
}

export function normalizeBroadcast(b: any): Broadcast {
  if (!b) {
    return {
      id: 0,
      created_by_telegram_id: 0,
      status: "UNKNOWN",
      content_type: null,
      content_preview: null,
      file_name: null,
      mime_type: null,
      file_size: null,
      button_selection: "none",
      recipient_count: 0,
      delivered_count: 0,
      failed_count: 0,
      blocked_count: 0,
      created_at: new Date().toISOString(),
      started_at: null,
      completed_at: null,
    };
  }

  return {
    id: Number(b.id) || 0,
    created_by_telegram_id: Number(b.created_by_telegram_id) || 0,
    status: typeof b.status === "string" ? b.status : "UNKNOWN",
    content_type: typeof b.content_type === "string" ? b.content_type : null,
    content_preview: typeof b.content_preview === "string" ? b.content_preview : null,
    file_name: typeof b.file_name === "string" ? b.file_name : null,
    mime_type: typeof b.mime_type === "string" ? b.mime_type : null,
    file_size: b.file_size !== undefined && b.file_size !== null ? Number(b.file_size) : null,
    button_selection: typeof b.button_selection === "string" ? b.button_selection : "none",
    recipient_count: Number(b.recipient_count) || 0,
    delivered_count: Number(b.delivered_count) || 0,
    failed_count: Number(b.failed_count) || 0,
    blocked_count: Number(b.blocked_count) || 0,
    created_at: typeof b.created_at === "string" ? b.created_at : new Date().toISOString(),
    started_at: typeof b.started_at === "string" ? b.started_at : null,
    completed_at: typeof b.completed_at === "string" ? b.completed_at : null,
  };
}

export function normalizeAIMessage(msg: any): AIMessage {
  if (!msg) {
    return {
      id: 0,
      role: "user",
      content: "",
      model_id: null,
      created_at: new Date().toISOString(),
    };
  }

  return {
    id: Number(msg.id) || 0,
    role: typeof msg.role === "string" ? msg.role : "user",
    content: typeof msg.content === "string" ? msg.content : "",
    model_id: typeof msg.model_id === "string" ? msg.model_id : null,
    created_at: typeof msg.created_at === "string" ? msg.created_at : new Date().toISOString(),
  };
}

export function compileErrorReport(
  errorMsg: string | null | undefined,
  currentRoute: string,
  role: string | null | undefined,
  locale: string | null | undefined,
  authState: string,
  profile: any,
  lastApiStatus?: number | null
): string {
  const profileKeys = profile ? Object.keys(profile).join(", ") : "N/A";
  
  const reportLines = [
    `=== Saved Chat Mini App Error Report ===`,
    `Error Message: ${errorMsg || "N/A"}`,
    `Current Route: ${currentRoute}`,
    `Role: ${role || "N/A"}`,
    `Locale: ${locale || "N/A"}`,
    `Auth State: ${authState}`,
    `Profile Schema Keys: [${profileKeys}]`,
    `Last API Status: ${lastApiStatus !== undefined && lastApiStatus !== null ? lastApiStatus : "N/A"}`,
    `Timestamp: ${new Date().toISOString()}`,
    `========================================`
  ];
  
  return reportLines.join("\n");
}

export function copyToClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text).then(() => true).catch(() => false);
  } else {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
      textArea.remove();
      return Promise.resolve(true);
    } catch (err) {
      textArea.remove();
      return Promise.resolve(false);
    }
  }
}
