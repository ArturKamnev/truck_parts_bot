// Type definitions for Telegram WebApp
export interface TelegramUser {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  language_code?: string;
}

export interface TelegramWebApp {
  ready(): void;
  expand(): void;
  close(): void;
  initData: string;
  initDataUnsafe: {
    query_id?: string;
    user?: TelegramUser;
    auth_date?: number;
    hash?: string;
  };
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

// Check if we are running in development or inside the actual Telegram client
export const isDev = import.meta.env.DEV;

// Safe retrieval of WebApp SDK
export const getTelegramWebApp = (): TelegramWebApp | null => {
  if (typeof window !== "undefined" && window.Telegram && window.Telegram.WebApp) {
    return window.Telegram.WebApp;
  }
  return null;
};

// Generates a local mock initData string based on role for testing in browser outside Telegram
export const getMockInitData = (role: "customer" | "manager" | "owner"): string => {
  const mockUsers = {
    customer: { id: 55555, first_name: "Mock", last_name: "Customer", username: "mock_customer" },
    manager: { id: 101, first_name: "Mock", last_name: "Manager", username: "mock_manager" },
    owner: { id: 999, first_name: "Mock", last_name: "Owner", username: "mock_owner" },
  };

  const user = mockUsers[role];
  const authDate = Math.floor(Date.now() / 1000);
  
  // Construct parameters matching query string format
  const query = `auth_date=${authDate}&user=${encodeURIComponent(JSON.stringify(user))}&hash=mock_hash_role_${role}`;
  return query;
};

export const initTelegramSDK = (): void => {
  const webApp = getTelegramWebApp();
  if (webApp) {
    try {
      webApp.ready();
      webApp.expand();
    } catch (e) {
      console.warn("Failed to initialize Telegram WebApp SDK:", e);
    }
  }
};
