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
  openTelegramLink(url: string): void;
  initData: string;
  initDataUnsafe: {
    query_id?: string;
    user?: TelegramUser;
    auth_date?: number;
    hash?: string;
  };
  platform?: string;
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

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

export interface TelegramLaunchContext {
  webApp: TelegramWebApp | null;
  initData: string;
}

export const safeInitTelegramWebApp = (webApp: TelegramWebApp | null): void => {
  if (!webApp) return;
  try {
    webApp.ready();
  } catch (e) {
    if (isDev) console.warn("Telegram WebApp ready() failed:", e);
  }
  try {
    webApp.expand();
  } catch (e) {
    if (isDev) console.warn("Telegram WebApp expand() failed:", e);
  }
};

// Poll and wait for Telegram WebApp to be injected/available.
export const waitForTelegramWebApp = (timeoutMs: number = 5000): Promise<TelegramWebApp | null> => {
  return new Promise((resolve) => {
    if (typeof window === "undefined") {
      resolve(null);
      return;
    }
    if (window.Telegram?.WebApp) {
      resolve(window.Telegram.WebApp);
      return;
    }
    const startTime = Date.now();
    const interval = window.setInterval(() => {
      if (window.Telegram?.WebApp) {
        window.clearInterval(interval);
        resolve(window.Telegram.WebApp);
      } else if (Date.now() - startTime >= timeoutMs) {
        window.clearInterval(interval);
        resolve(null);
      }
    }, 75);
  });
};

export const waitForTelegramLaunchContext = async (
  timeoutMs: number = 6500
): Promise<TelegramLaunchContext> => {
  const startedAt = Date.now();
  let delay = 80;
  let webApp = getTelegramWebApp();

  while (Date.now() - startedAt < timeoutMs) {
    webApp = getTelegramWebApp() || (await waitForTelegramWebApp(Math.min(delay, 500)));
    safeInitTelegramWebApp(webApp);

    const initData = webApp?.initData || "";
    if (initData.length > 0) {
      return { webApp, initData };
    }

    await sleep(delay);
    delay = Math.min(Math.round(delay * 1.6), 900);
  }

  webApp = getTelegramWebApp();
  safeInitTelegramWebApp(webApp);
  return { webApp, initData: webApp?.initData || "" };
};

// Generates a local mock initData string based on role for testing in browser outside Telegram
export const getMockInitData = (role: "customer" | "manager" | "owner" | "co_owner"): string => {
  const mockUsers = {
    customer: { id: 55555, first_name: "Mock", last_name: "Customer", username: "mock_customer" },
    manager: { id: 101, first_name: "Mock", last_name: "Manager", username: "mock_manager" },
    owner: { id: 999, first_name: "Mock", last_name: "Owner", username: "mock_owner" },
    co_owner: { id: 202, first_name: "Mock", last_name: "CoOwner", username: "mock_co_owner" },
  };

  const user = mockUsers[role];
  const authDate = Math.floor(Date.now() / 1000);
  
  // Construct parameters matching query string format
  const query = `auth_date=${authDate}&user=${encodeURIComponent(JSON.stringify(user))}&hash=mock_hash_role_${role}`;
  return query;
};

export const initTelegramSDK = (): void => {
  const webApp = getTelegramWebApp();
  safeInitTelegramWebApp(webApp);
};
