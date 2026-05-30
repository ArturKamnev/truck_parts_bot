import { apiRequest } from "./client";
import { normalizeUserProfile } from "../utils/normalization";

export interface UserProfile {
  telegram_user_id: number;
  role: "customer" | "manager" | "owner" | "co_owner";
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
  preferred_language: "ru" | "en" | "ky" | string | null;
}

export interface AuthResponse {
  token: string;
  profile: UserProfile;
}

export const authenticateTelegram = async (initData: string): Promise<AuthResponse> => {
  const res = await apiRequest<AuthResponse>("/api/auth/telegram", {
    method: "POST",
    body: JSON.stringify({ initData }),
  });
  return {
    token: res.token,
    profile: normalizeUserProfile(res.profile),
  };
};

export const getMe = async (): Promise<UserProfile> => {
  const profile = await apiRequest<UserProfile>("/api/me");
  return normalizeUserProfile(profile);
};

export const updateLanguage = async (language: "ru" | "en" | "ky"): Promise<string> => {
  return apiRequest<string>("/api/profile/language", {
    method: "POST",
    body: JSON.stringify({ language }),
  });
};

