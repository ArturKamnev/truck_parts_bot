import { apiRequest } from "./client";

export interface UserProfile {
  telegram_user_id: number;
  role: "customer" | "manager" | "owner";
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  display_name: string;
  broadcasts_enabled: boolean;
  miniapp_url: string | null;
  customer_mode?: "AI_CHAT" | "WAITING_MANAGER" | "MANAGER_CHAT" | string;
  selected_ticket_id: number | null;
  feature_flags: {
    ai_streaming_enabled?: boolean;
    [key: string]: any;
  };
}

export interface AuthResponse {
  token: string;
  profile: UserProfile;
}

export const authenticateTelegram = async (initData: string): Promise<AuthResponse> => {
  return apiRequest<AuthResponse>("/api/auth/telegram", {
    method: "POST",
    body: JSON.stringify({ initData }),
  });
};

export const getMe = async (): Promise<UserProfile> => {
  return apiRequest<UserProfile>("/api/me");
};
