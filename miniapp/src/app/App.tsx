import React, { useEffect, useState } from "react";
import { getTelegramWebApp, getMockInitData, initTelegramSDK } from "../telegram/webapp";
import { authenticateTelegram, getMe } from "../api/auth";
import { type UserProfile } from "../api/auth";
import { clearStoredToken, getStoredToken, setStoredToken, onAuthError, type ApiError } from "../api/client";

// Import Pages & Shell Components
import { LoadingPage } from "../pages/LoadingPage";
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

  const isDev = import.meta.env.DEV;

  const handleAuthentication = async (initData: string, fromMock = false) => {
    try {
      setLoading(true);
      setError(null);
      
      // 1. Submit initData to POST /api/auth/telegram to get short-lived session token
      const authData = await authenticateTelegram(initData);
      setStoredToken(authData.token);
      setProfile(authData.profile);
      setIsMockActive(fromMock);
    } catch (err) {
      setError(err as ApiError);
      clearStoredToken();
    } finally {
      setLoading(false);
    }
  };

  const initializeApp = async () => {
    initTelegramSDK();
    const webApp = getTelegramWebApp();
    const storedToken = getStoredToken();

    if (storedToken) {
      try {
        setLoading(true);
        setError(null);
        // Load current profile using the stored session token
        const userProfile = await getMe();
        setProfile(userProfile);
        // If it starts with 'mock_', mark mock mode active
        setIsMockActive(storedToken.includes(".mock_") || !webApp);
      } catch (err) {
        // Stale or expired token
        clearStoredToken();
        setError(err as ApiError);
      } finally {
        setLoading(false);
      }
      return;
    }

    // No stored token: check for Telegram initData
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
          message: "Please open this application inside the Telegram Mobile app.",
        });
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    initializeApp();

    // Listen for 401 Unauthorized token expirations to log out cleanly
    const unsubscribe = onAuthError(() => {
      setProfile(null);
      setSelectedTicketId(null);
      setIsMockActive(false);
      setError({
        status: 401,
        message: "Your session has expired. Please reload the app.",
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
