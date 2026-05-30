// Fetch-based API client for communicating with FastAPI backend
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

    if (response.status === 401) {
      triggerAuthError();
      throw { status: 401, message: "Unauthorized / Expired session" } as ApiError;
    }

    if (response.status === 403) {
      throw { status: 403, message: "Forbidden: Access denied" } as ApiError;
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
    throw { status: 0, message: "Network connection failure. Make sure server is running." } as ApiError;
  }
};
