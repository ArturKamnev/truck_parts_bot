import React, { useEffect, useState } from "react";
import { getTelegramWebApp, getMockInitData, initTelegramSDK } from "../telegram/webapp";
import { authenticateTelegram, getMe } from "../api/auth";
import { type UserProfile } from "../api/auth";
import { clearStoredToken, getStoredToken, setStoredToken, onAuthError, type ApiError } from "../api/client";

// Import Pages & Shell Components
import { LoadingPage, type DiagnosticsData } from "../pages/LoadingPage";
import { TopBar } from "../components/TopBar";
import { CustomerHomePage } from "../pages/CustomerHomePage";
import { ManagerDashboardPage } from "../pages/ManagerDashboardPage";
import { OwnerDashboardPage } from "../pages/OwnerDashboardPage";
import { TicketChatPage } from "../pages/TicketChatPage";

export const App: React.FC = () => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null);
  const [isMockActive, setIsMockActive] = useState(false);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsData | null>(null);

  const isDev = import.meta.env.DEV;

  const handleAuthentication = async (initData: string, fromMock = false) => {
    setDiagnostics(prev => prev ? { ...prev, authAttempted: true } : null);
    try {
      setLoading(true);
      setError(null);
      
      // 1. Submit initData to POST /api/auth/telegram to get short-lived session token
      const authData = await authenticateTelegram(initData);
      setStoredToken(authData.token);
      setProfile(authData.profile);
      setIsMockActive(fromMock);
    } catch (err) {
      const apiErr = err as ApiError;
      setDiagnostics(prev => prev ? {
        ...prev,
        errorStatus: apiErr.status,
        errorType: apiErr.message || "Authentication Failed"
      } : null);

      let errMsg = "Не удалось подключиться к серверу Mini App.";
      if (apiErr.status === 401 || apiErr.status === 403) {
        errMsg = "Сессия Telegram недействительна. Откройте приложение заново из бота.";
      }

      setError({
        status: apiErr.status,
        message: errMsg,
      });
      clearStoredToken();
    } finally {
      setLoading(false);
    }
  };

  const initializeApp = async () => {
    initTelegramSDK();
    const webApp = getTelegramWebApp();
    const storedToken = getStoredToken();

    setError(null);
    setLoading(true);

    const hasTg = typeof window !== "undefined" && !!window.Telegram;
    const hasWebApp = !!webApp;
    const initDataLen = webApp?.initData ? webApp.initData.length : 0;
    const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

    const currentDiagnostics: DiagnosticsData = {
      apiBaseUrl,
      telegramExists: hasTg,
      webAppExists: hasWebApp,
      platform: (webApp?.initDataUnsafe as any)?.platform || (webApp as any)?.platform || null,
      initDataLength: initDataLen,
      authAttempted: false,
      errorStatus: null,
      errorType: null,
    };
    setDiagnostics(currentDiagnostics);

    if (storedToken) {
      try {
        // Load current profile using the stored session token
        const userProfile = await getMe();
        setProfile(userProfile);
        // If it starts with 'mock_', mark mock mode active
        setIsMockActive(storedToken.includes(".mock_") || !webApp);
        setLoading(false);
        return;
      } catch (err) {
        // Stale or expired token
        clearStoredToken();
        const apiErr = err as ApiError;
        currentDiagnostics.errorStatus = apiErr.status;
        currentDiagnostics.errorType = apiErr.message || "Token Session Validation Failed";
        setDiagnostics({ ...currentDiagnostics });
        // Fall through to try initData authorization
      }
    }

    // Check for Telegram initData
    if (webApp && webApp.initData) {
      await handleAuthentication(webApp.initData, false);
    } else {
      // Missing initData:
      if (isDev) {
        // Show local role selection panel
        setLoading(false);
      } else {
        // Enforce Telegram client in production
        setError({
          status: 403,
          message: "Откройте приложение через кнопку Mini App в Telegram-боте.",
        });
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    initializeApp();

    // Listen for 401/403 Unauthorized token expirations to log out cleanly
    const unsubscribe = onAuthError(() => {
      setProfile(null);
      setSelectedTicketId(null);
      setIsMockActive(false);
      setError({
        status: 401,
        message: "Сессия Telegram недействительна. Откройте приложение заново из бота.",
      });
    });

    return () => unsubscribe();
  }, []);

  const handleSelectMockRole = async (role: "customer" | "manager" | "owner") => {
    const mockInitData = getMockInitData(role);
    // Local mock tokens will contain '.mock_' for detection
    await handleAuthentication(mockInitData, true);
  };

  const handleLogout = () => {
    clearStoredToken();
    setProfile(null);
    setSelectedTicketId(null);
    setIsMockActive(false);
    setError(null);
    // Reload to prompt authentication choice or SDK check
    initializeApp();
  };

  // --- Rendering Routing Switcher ---
  if (loading || !profile) {
    return (
      <LoadingPage
        error={error}
        onRetry={initializeApp}
        isDev={isDev && !getTelegramWebApp()?.initData}
        onSelectMockRole={handleSelectMockRole}
        diagnostics={diagnostics}
      />
    );
  }

  // Active chat page view
  if (selectedTicketId !== null) {
    return (
      <TicketChatPage
        ticketId={selectedTicketId}
        viewerRole={profile.role}
        onBack={() => setSelectedTicketId(null)}
      />
    );
  }

  // Main layouts
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", width: "100%" }}>
      <TopBar profile={profile} isMockActive={isMockActive} onLogout={handleLogout} />
      
      <main style={{ flex: 1, overflow: "hidden" }}>
        {profile.role === "customer" && (
          <CustomerHomePage onSelectTicket={setSelectedTicketId} />
        )}
        {profile.role === "manager" && (
          <ManagerDashboardPage onSelectTicket={setSelectedTicketId} />
        )}
        {profile.role === "owner" && (
          <OwnerDashboardPage onSelectTicket={setSelectedTicketId} />
        )}
      </main>
    </div>
  );
};
export default App;
