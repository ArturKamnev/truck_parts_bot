// Fetch-based API client for communicating with FastAPI backend
import { waitForTelegramLaunchContext } from "../telegram/webapp";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

export interface ApiError {
  status: number;
  message: string;
}

// Token Storage Key
const TOKEN_KEY = "tma_session_token";

export const getStoredToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY);
};

export const setStoredToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token);
};

export const clearStoredToken = (): void => {
  localStorage.removeItem(TOKEN_KEY);
};

// Event listener for token expiration
type AuthCallback = () => void;
const authErrorListeners = new Set<AuthCallback>();

export const onAuthError = (callback: AuthCallback): (() => void) => {
  authErrorListeners.add(callback);
  return () => authErrorListeners.delete(callback);
};

const triggerAuthError = (): void => {
  clearStoredToken();
  authErrorListeners.forEach((cb) => cb());
};

// Generic fetch wrapper
export const apiRequest = async <T>(
  path: string,
  options: RequestInit = {}
): Promise<T> => {
  const url = `${API_BASE_URL}${path}`;
  const token = getStoredToken();

  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const config: RequestInit = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);

    if ((response.status === 401 || response.status === 403) && path !== "/api/auth/telegram") {
      if (typeof window !== "undefined") {
        try {
          clearStoredToken();
          const { initData } = await waitForTelegramLaunchContext(3500);
          if (!initData) throw new Error("Missing Telegram initData for silent re-auth");
          const authRes = await fetch(`${API_BASE_URL}/api/auth/telegram`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ initData }),
          });

          if (authRes.ok) {
            const authData = await authRes.json();
            setStoredToken(authData.token);
            localStorage.setItem("tma_user_profile", JSON.stringify(authData.profile));

            const newHeaders = new Headers(options.headers);
            newHeaders.set("Authorization", `Bearer ${authData.token}`);
            if (!(options.body instanceof FormData) && !newHeaders.has("Content-Type")) {
              newHeaders.set("Content-Type", "application/json");
            }
            const newConfig = {
              ...options,
              headers: newHeaders,
            };
            return await apiRequest<T>(path, newConfig);
          }
        } catch (reauthErr) {
          if (import.meta.env.DEV) console.warn("Silent re-authentication failed:", reauthErr);
        }
      }

      triggerAuthError();
      localStorage.removeItem("tma_user_profile");
      const errMsg = "Telegram-сессия недействительна. Откройте приложение заново из бота.";
      throw { status: response.status, message: errMsg } as ApiError;
    }

    if (!response.ok) {
      let message = `API Error: ${response.statusText}`;
      try {
        const errorData = await response.json();
        message = errorData.detail || message;
      } catch (e) {
        // ignore
      }
      throw { status: response.status, message } as ApiError;
    }

    // Health check returns raw JSON, others too
    return (await response.json()) as T;
  } catch (error) {
    if ((error as ApiError).status) {
      throw error;
    }
    // Network errors
    throw { status: 0, message: "API unreachable or CORS/config error. Check API base URL and server CORS settings." } as ApiError;
  }
};
