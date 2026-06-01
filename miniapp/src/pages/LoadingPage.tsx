import React, { useState } from "react";
import { RotateCcw, Shield, Lock, WifiOff, AlertTriangle } from "lucide-react";
import { type ApiError } from "../api/client";
import { t } from "../i18n";
import { compileErrorReport, copyToClipboard } from "../utils/normalization";

export interface DiagnosticsData {
  apiBaseUrl: string;
  telegramExists: boolean;
  webAppExists: boolean;
  platform: string | null;
  initDataLength: number;
  authAttempted: boolean;
  errorStatus: number | string | null;
  errorType: string | null;
  currentRole?: string | null;
  currentLocale?: string | null;
  currentRoute?: string;
  lastErrorSummary?: string | null;
}

interface LoadingPageProps {
  authState:
    | "booting"
    | "waitingTelegram"
    | "authenticating"
    | "loadingProfile"
    | "ready"
    | "missingInitData"
    | "apiUnavailable"
    | "invalidSession"
    | "fatalRenderError"
    | "unsupportedRole";
  error: ApiError | null;
  onRetry: () => void;
  isDev: boolean;
  onSelectMockRole?: (role: "customer" | "manager" | "owner" | "co_owner") => void;
  diagnostics?: DiagnosticsData | null;
  locale?: string;
}

const getActiveLocale = (): string => {
  try {
    const cached = localStorage.getItem("tma_user_profile");
    if (cached) {
      const parsed = JSON.parse(cached);
      if (parsed?.preferred_language) {
        return parsed.preferred_language;
      }
    }
  } catch {
    // ignore
  }
  
  if (typeof window !== "undefined") {
    const tgLang = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code;
    if (typeof tgLang === "string") {
      const lang = tgLang.toLowerCase().slice(0, 2);
      if (["ru", "en", "ky"].includes(lang)) return lang;
      if (lang === "kg") return "ky";
    }
  }
  return "ru";
};

const sanitizeMessage = (msg: string | undefined | null): string => {
  if (!msg) return "";
  let clean = msg.replace(/eyJ[a-zA-Z0-9-_=]+\.[a-zA-Z0-9-_=]+\.?[a-zA-Z0-9-_.+/=]*/g, "[REDACTED_JWT]");
  clean = clean.replace(/initData=[^&\s]+/g, "initData=[REDACTED]");
  clean = clean.replace(/query_id=[^&\s]+/g, "query_id=[REDACTED]");
  clean = clean.replace(/hash=[^&\s]+/g, "hash=[REDACTED]");
  clean = clean.replace(/Bearer\s+[a-zA-Z0-9-_.]+/g, "Bearer [REDACTED]");
  return clean;
};

export const LoadingPage: React.FC<LoadingPageProps> = ({
  authState,
  onRetry,
  isDev,
  onSelectMockRole,
  diagnostics,
  error,
  locale: localeProp,
}) => {
  const locale = localeProp || getActiveLocale();
  const [copied, setCopied] = useState(false);

  const handleCopyReport = () => {
    let profile = null;
    try {
      const cached = localStorage.getItem("tma_user_profile");
      if (cached) profile = JSON.parse(cached);
    } catch {}

    const errorMsg = error?.message || error?.toString();
    const reportText = compileErrorReport(
      errorMsg,
      diagnostics?.currentRoute || window.location.pathname,
      diagnostics?.currentRole || null,
      locale,
      authState,
      profile,
      diagnostics?.errorStatus !== null && diagnostics?.errorStatus !== undefined ? Number(diagnostics?.errorStatus) : null
    );

    copyToClipboard(reportText).then((ok) => {
      if (ok) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } else {
        alert(t("error.copy_report_failed", locale));
      }
    });
  };


  // Determine view based on authState
  const isLoadingState = ["booting", "waitingTelegram", "authenticating", "loadingProfile"].includes(authState);

  let statusText = t("common.loading", locale);
  if (authState === "booting") statusText = t("loading.booting", locale);
  else if (authState === "waitingTelegram") statusText = t("loading.waiting_telegram", locale);
  else if (authState === "authenticating") statusText = t("loading.authenticating", locale);
  else if (authState === "loadingProfile") statusText = t("loading.loading_profile", locale);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        width: "100%",
        padding: "24px",
        backgroundColor: "hsl(var(--bg-secondary-hsl))",
        color: "hsl(var(--text-primary-hsl))",
        boxSizing: "border-box",
      }}
    >
      {isLoadingState ? (
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
            <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff" }}>{statusText}</h3>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: "20px" }}>
          {authState === "missingInitData" && (
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
                  {t("error.restricted_access", locale)}
                </h2>
                <p style={{ fontSize: "14px", color: "hsl(var(--text-hint-hsl))", maxWidth: "280px", lineHeight: "1.4" }}>
                  {t("error.restricted_access_desc", locale)}
                </p>
              </div>
            </>
          )}

          {authState === "invalidSession" && (
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
                  {t("error.stale_session_title", locale)}
                </h2>
                <p style={{ fontSize: "14px", color: "hsl(var(--text-hint-hsl))", maxWidth: "280px", lineHeight: "1.4" }}>
                  {t("error.stale_session", locale)}
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
                  border: "none",
                  borderRadius: "var(--radius-md)",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
                  boxShadow: "var(--shadow-md)"
                }}
              >
                <RotateCcw size={16} />
                {t("common.retry_auth", locale)}
              </button>
            </>
          )}

          {authState === "apiUnavailable" && (
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
                  {t("error.connection_failure_title", locale)}
                </h2>
                <p style={{ fontSize: "14px", color: "hsl(var(--text-hint-hsl))", maxWidth: "280px", lineHeight: "1.4" }}>
                  {t("error.connection_failure", locale)}
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
                  border: "none",
                  borderRadius: "var(--radius-md)",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
                  boxShadow: "var(--shadow-md)"
                }}
              >
                <RotateCcw size={16} />
                {t("common.retry", locale)}
              </button>
            </>
          )}

          {authState === "unsupportedRole" && (
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
                  {t("error.unsupported_role", locale)}
                </h2>
                <p style={{ fontSize: "14px", color: "hsl(var(--text-hint-hsl))", maxWidth: "280px", lineHeight: "1.4" }}>
                  {t("error.unsupported_role_desc", locale)}
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
                  border: "none",
                  borderRadius: "var(--radius-md)",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
                  boxShadow: "var(--shadow-md)"
                }}
              >
                <RotateCcw size={16} />
                {t("common.retry_auth", locale)}
              </button>
            </>
          )}

          {authState === "fatalRenderError" && (
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
                <AlertTriangle size={40} style={{ color: "hsl(var(--danger-hsl))" }} />
              </div>
              <div>
                <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px", color: "#fff" }}>
                  {t("error.critical_title", locale)}
                </h2>
                <p style={{ fontSize: "14px", color: "hsl(var(--text-hint-hsl))", maxWidth: "280px", lineHeight: "1.4" }}>
                  {t("error.critical_desc", locale)}
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
                  border: "none",
                  borderRadius: "var(--radius-md)",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
                  boxShadow: "var(--shadow-md)"
                }}
              >
                <RotateCcw size={16} />
                {t("common.reload", locale)}
              </button>
            </>
          )}
          <button
            onClick={handleCopyReport}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 20px",
              backgroundColor: "rgba(82, 136, 193, 0.15)",
              color: "rgb(112, 172, 237)",
              border: "1px dashed rgba(82, 136, 193, 0.3)",
              borderRadius: "var(--radius-md)",
              fontWeight: 600,
              fontSize: "13px",
              cursor: "pointer",
              marginTop: "16px",
            }}
          >
            {copied ? t("common.copied", locale) : t("common.copy_error_report", locale)}
          </button>
        </div>
      )}

      {/* Diagnostics Panel - Collapsible & Safe */}
      {isDev && diagnostics && (
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
            {t("loading.diagnostics", locale)}
          </summary>
          <div style={{ marginTop: "8px", display: "flex", flexDirection: "column", gap: "4px" }}>
            <div>{t("loading.api_base", locale)}: {sanitizeMessage(diagnostics.apiBaseUrl)}</div>
            <div>Telegram SDK: {diagnostics.telegramExists ? t("common.yes", locale) : t("common.no", locale)}</div>
            <div>WebApp SDK: {diagnostics.webAppExists ? t("common.yes", locale) : t("common.no", locale)}</div>
            <div>{t("loading.platform", locale)}: {diagnostics.platform || t("stats.not_available", locale)}</div>
            <div>initData: {diagnostics.initDataLength}</div>
            <div>{t("loading.auth_attempted", locale)}: {diagnostics.authAttempted ? t("common.yes", locale) : t("common.no", locale)}</div>
            <div>{t("loading.last_status", locale)}: {diagnostics.errorStatus !== null ? diagnostics.errorStatus : t("stats.not_available", locale)}</div>
            <div>{t("loading.error_type", locale)}: {sanitizeMessage(diagnostics.errorType || t("stats.not_available", locale))}</div>
            <div>{t("loading.current_role", locale)}: {diagnostics.currentRole || t("stats.not_available", locale)}</div>
            <div>{t("loading.current_locale", locale)}: {diagnostics.currentLocale || t("stats.not_available", locale)}</div>
            <div>{t("loading.current_route", locale)}: {diagnostics.currentRoute || "/"}</div>
            {diagnostics.lastErrorSummary && (
              <div style={{ color: "#ff7b72" }}>{t("loading.last_error", locale)}: {sanitizeMessage(diagnostics.lastErrorSummary)}</div>
            )}
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
              {t("loading.dev_mock_routing", locale)}
            </span>
          </div>
          <p style={{ fontSize: "11px", color: "hsl(var(--text-hint-hsl))", textAlign: "center", marginBottom: "4px" }}>
            {t("loading.dev_mock_desc", locale)}
          </p>
          <div style={{ display: "flex", gap: "8px", width: "100%" }}>
            {(["customer", "manager", "owner", "co_owner"] as const).map((role) => (
              <button
                key={role}
                onClick={() => onSelectMockRole(role)}
                style={{
                  flex: 1,
                  padding: "8px 0",
                  backgroundColor: "hsl(var(--border-hsl))",
                  border: "none",
                  color: "#fff",
                  borderRadius: "var(--radius-sm)",
                  fontSize: "12px",
                  fontWeight: 600,
                  textTransform: "capitalize",
                  cursor: "pointer",
                }}
              >
                {t(`role.${role}`, locale)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
