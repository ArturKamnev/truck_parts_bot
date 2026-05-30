import React from "react";
import { AlertCircle, RotateCcw, Shield, Lock, WifiOff } from "lucide-react";
import { type ApiError } from "../api/client";

interface LoadingPageProps {
  error: ApiError | null;
  onRetry: () => void;
  isDev: boolean;
  onSelectMockRole?: (role: "customer" | "manager" | "owner") => void;
}

export const LoadingPage: React.FC<LoadingPageProps> = ({
  error,
  onRetry,
  isDev,
  onSelectMockRole,
}) => {
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
        error.status === 401 ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: "20px" }}>
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
              <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px", color: "#fff" }}>Session Expired</h2>
              <p style={{ fontSize: "14px", color: "hsl(var(--text-hint-hsl))", maxWidth: "280px", lineHeight: "1.4" }}>
                Your Telegram security session has expired or is invalid. Please reload the app to authenticate.
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
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: "20px" }}>
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
              {error.status === 0 ? (
                <WifiOff size={40} style={{ color: "hsl(var(--warning-hsl))" }} />
              ) : (
                <AlertCircle size={40} style={{ color: "hsl(var(--danger-hsl))" }} />
              )}
            </div>
            <div>
              <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px", color: "#fff" }}>
                {error.status === 0 ? "Connection Offline" : "Connection Failed"}
              </h2>
              <p style={{ fontSize: "14px", color: "hsl(var(--text-hint-hsl))", maxWidth: "280px", lineHeight: "1.4" }}>
                {error.message}
              </p>
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
          </div>
        )
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
