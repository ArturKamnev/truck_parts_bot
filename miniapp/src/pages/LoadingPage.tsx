import React from "react";
import { RotateCcw, Shield, Lock, WifiOff } from "lucide-react";
import { type ApiError } from "../api/client";

export interface DiagnosticsData {
  apiBaseUrl: string;
  telegramExists: boolean;
  webAppExists: boolean;
  platform: string | null;
  initDataLength: number;
  authAttempted: boolean;
  errorStatus: number | null;
  errorType: string | null;
}

interface LoadingPageProps {
  error: ApiError | null;
  onRetry: () => void;
  isDev: boolean;
  onSelectMockRole?: (role: "customer" | "manager" | "owner") => void;
  diagnostics?: DiagnosticsData | null;
}

export const LoadingPage: React.FC<LoadingPageProps> = ({
  error,
  onRetry,
  isDev,
  onSelectMockRole,
  diagnostics,
}) => {
  // Determine precise error state
  const isMissingInitData =
    error &&
    (error.message.includes("кнопку Mini App") ||
      error.message.includes("через кнопку Mini App") ||
      (error.status === 403 && !localStorage.getItem("tma_session_token")));

  const isInvalidSession =
    error &&
    (error.message.includes("недействительна") ||
      error.message.includes("Сессия Telegram") ||
      error.status === 401 ||
      (error.status === 403 && !!localStorage.getItem("tma_session_token")));

  const isNetworkError =
    error &&
    (error.status === 0 ||
      error.message.includes("подключиться к серверу") ||
      (!isMissingInitData && !isInvalidSession));

  return (
    <div
      className="animate-fade-in"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        padding: "24px",
        backgroundColor: "hsl(var(--bg-secondary-hsl))",
        color: "hsl(var(--text-primary-hsl))",
      }}
    >
      {error ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: "20px" }}>
          {isMissingInitData && (
            <>
              <div style={{
                width: "80px",
                height: "80px",
                borderRadius: "50%",
                backgroundColor: "rgba(255, 179, 0, 0.1)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "8px"
              }}>
                <Shield size={40} style={{ color: "hsl(var(--warning-hsl))" }} />
              </div>
              <div>
                <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px", color: "#fff" }}>
                  Доступ ограничен
                </h2>
                <p style={{ fontSize: "14px", color: "hsl(var(--text-hint-hsl))", maxWidth: "280px", lineHeight: "1.4" }}>
                  Откройте приложение через кнопку Mini App в Telegram-боте.
                </p>
              </div>
            </>
          )}

          {isInvalidSession && (
            <>
              <div style={{
                width: "80px",
                height: "80px",
                borderRadius: "50%",
                backgroundColor: "rgba(255, 77, 77, 0.1)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "8px"
              }}>
                <Lock size={40} style={{ color: "hsl(var(--danger-hsl))" }} />
              </div>
              <div>
                <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px", color: "#fff" }}>
                  Сессия недействительна
                </h2>
                <p style={{ fontSize: "14px", color: "hsl(var(--text-hint-hsl))", maxWidth: "280px", lineHeight: "1.4" }}>
                  Telegram-сессия недействительна. Откройте приложение заново из бота.
                </p>
              </div>
              <button
                onClick={() => window.location.reload()}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "12px 24px",
                  backgroundColor: "hsl(var(--accent-hsl))",
                  color: "#fff",
                  borderRadius: "var(--radius-md)",
                  fontWeight: 600,
                  fontSize: "14px",
                  boxShadow: "var(--shadow-md)"
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "hsl(var(--accent-hover-hsl))")}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "hsl(var(--accent-hsl))")}
              >
                <RotateCcw size={16} />
                Reload Application
              </button>
            </>
          )}

          {isNetworkError && (
            <>
              <div style={{
                width: "80px",
                height: "80px",
                borderRadius: "50%",
                backgroundColor: "rgba(255, 255, 255, 0.05)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: "8px"
              }}>
                <WifiOff size={40} style={{ color: "hsl(var(--warning-hsl))" }} />
              </div>
              <div>
                <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px", color: "#fff" }}>
                  Ошибка подключения
                </h2>
                <p style={{ fontSize: "14px", color: "hsl(var(--text-hint-hsl))", maxWidth: "280px", lineHeight: "1.4" }}>
                  Не удалось подключиться к серверу Mini App.
                </p>
                {isDev && (
                  <p style={{ fontSize: "11px", color: "hsl(var(--warning-hsl))", marginTop: "8px", maxWidth: "280px" }}>
                    CORS/config error: Check VITE_API_BASE_URL, local server logs, and CORS configurations.
                  </p>
                )}
              </div>
              <button
                onClick={onRetry}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "12px 24px",
                  backgroundColor: "hsl(var(--accent-hsl))",
                  color: "#fff",
                  borderRadius: "var(--radius-md)",
                  fontWeight: 600,
                  fontSize: "14px",
                  boxShadow: "var(--shadow-md)"
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "hsl(var(--accent-hover-hsl))")}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "hsl(var(--accent-hsl))")}
              >
                <RotateCcw size={16} />
                Retry Connection
              </button>
            </>
          )}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "20px" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "50%",
              border: "3px solid hsl(var(--border-hsl))",
              borderTopColor: "hsl(var(--accent-hsl))",
              animation: "skeleton-loading 1.2s linear infinite",
            }}
          />
          <div style={{ textAlign: "center" }}>
            <h3 style={{ fontSize: "16px", fontWeight: 600 }}>Securing Connection</h3>
            <p style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))", marginTop: "4px" }}>
              Authenticating with Telegram secure keys...
            </p>
          </div>
        </div>
      )}

      {/* Diagnostics Panel - Shown ONLY in development */}
      {isDev && error && diagnostics && (
        <details
          style={{
            marginTop: "24px",
            textAlign: "left",
            width: "100%",
            maxWidth: "320px",
            fontFamily: "monospace",
            fontSize: "11px",
            backgroundColor: "rgba(255, 255, 255, 0.03)",
            border: "1px solid hsl(var(--border-hsl))",
            borderRadius: "var(--radius-sm)",
            padding: "8px 12px",
            color: "hsl(var(--text-hint-hsl))",
          }}
        >
          <summary style={{ cursor: "pointer", fontWeight: 600, color: "hsl(var(--accent-hsl))", userSelect: "none" }}>
            Diagnostics Info
          </summary>
          <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "4px" }}>
            <div>API Base: {diagnostics.apiBaseUrl}</div>
            <div>Telegram SDK: {diagnostics.telegramExists ? "Loaded" : "Missing"}</div>
            <div>WebApp SDK: {diagnostics.webAppExists ? "Available" : "Missing"}</div>
            <div>Platform: {diagnostics.platform || "N/A"}</div>
            <div>initData Length: {diagnostics.initDataLength}</div>
            <div>Auth Attempted: {diagnostics.authAttempted ? "Yes" : "No"}</div>
            <div>Last Status: {diagnostics.errorStatus !== null ? diagnostics.errorStatus : "None"}</div>
            <div>Error Type: {diagnostics.errorType || "None"}</div>
          </div>
        </details>
      )}

      {/* Local Mock Auth Panel - Only shown in development */}
      {isDev && onSelectMockRole && (
        <div
          style={{
            marginTop: "64px",
            padding: "16px",
            backgroundColor: "hsl(var(--card-bg-hsl))",
            border: "1px solid hsl(var(--border-hsl))",
            borderRadius: "var(--radius-md)",
            width: "100%",
            maxWidth: "320px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "hsl(var(--warning-hsl))" }}>
            <Shield size={16} />
            <span style={{ fontSize: "12px", fontWeight: 700, letterSpacing: "0.05em" }}>
              LOCAL DEV MOCK ROUTING
            </span>
          </div>
          <p style={{ fontSize: "11px", color: "hsl(var(--text-hint-hsl))", textAlign: "center", marginBottom: "4px" }}>
            No Telegram environment detected. Choose a mock role to test the Mini App interfaces:
          </p>
          <div style={{ display: "flex", gap: "8px", width: "100%" }}>
            {(["customer", "manager", "owner"] as const).map((role) => (
              <button
                key={role}
                onClick={() => onSelectMockRole(role)}
                style={{
                  flex: 1,
                  padding: "8px 0",
                  backgroundColor: "hsl(var(--border-hsl))",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "12px",
                  fontWeight: 600,
                  textTransform: "capitalize",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "hsl(var(--accent-hsl))")}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "hsl(var(--border-hsl))")}
              >
                {role}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
