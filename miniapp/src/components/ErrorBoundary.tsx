import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";
import { t } from "../i18n";
import { compileErrorReport, copyToClipboard } from "../utils/normalization";

interface Props {
  children: ReactNode;
  apiBaseUrl?: string;
  locale?: string;
  role?: string;
  hasProfile?: boolean;
  onDidCatch?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  copied: boolean;
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
  } catch (e) {
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

const sanitizeMessage = (msg: string | null | undefined): string => {
  if (!msg) return "";
  // Strip JWTs
  let clean = msg.replace(/eyJ[a-zA-Z0-9-_=]+\.[a-zA-Z0-9-_=]+\.?[a-zA-Z0-9-_.+/=]*/g, "[REDACTED_JWT]");
  // Strip initData url parameters
  clean = clean.replace(/initData=[^&\s]+/g, "initData=[REDACTED]");
  clean = clean.replace(/query_id=[^&\s]+/g, "query_id=[REDACTED]");
  clean = clean.replace(/hash=[^&\s]+/g, "hash=[REDACTED]");
  // Strip authorization header values
  clean = clean.replace(/Bearer\s+[a-zA-Z0-9-_.]+/g, "Bearer [REDACTED]");
  return clean;
};

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
    copied: false,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    if (this.props.onDidCatch) {
      this.props.onDidCatch(error, errorInfo);
    }
    if (import.meta.env.DEV) {
      console.error("[ErrorBoundary] Caught critical runtime error:", error, errorInfo);
    }
    try {
      localStorage.setItem("tma_last_crash_reason", JSON.stringify({
        message: error.message,
        stack: errorInfo.componentStack,
        timestamp: new Date().toISOString()
      }));
    } catch(e){}
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleRetryAuth = () => {
    localStorage.removeItem("tma_session_token");
    localStorage.removeItem("tma_user_profile");
    window.location.reload();
  };

  private handleCopyReport = () => {
    let profile = null;
    let cachedRole = this.props.role;
    try {
      const cached = localStorage.getItem("tma_user_profile");
      if (cached) {
        profile = JSON.parse(cached);
        if (!cachedRole) cachedRole = profile.role;
      }
    } catch (e) {}

    const locale = this.props.locale || getActiveLocale();
    const errorMsg = this.state.error?.message || this.state.error?.toString();
    const reportText = compileErrorReport(
      errorMsg,
      window.location.pathname,
      cachedRole,
      locale,
      "fatalRenderError",
      profile,
      null
    );

    copyToClipboard(reportText).then((ok) => {
      if (ok) {
        this.setState({ copied: true });
        setTimeout(() => this.setState({ copied: false }), 2000);
      } else {
        alert(t("error.copy_report_failed", locale));
      }
    });
  };

  public render() {
    if (this.state.hasError) {
      const isDev = import.meta.env.DEV;
      const locale = this.props.locale || getActiveLocale();
      
      let cachedRole = this.props.role;
      let hasProfile = this.props.hasProfile;
      try {
        const cached = localStorage.getItem("tma_user_profile");
        if (cached) {
          const parsed = JSON.parse(cached);
          if (!cachedRole) cachedRole = parsed.role;
          if (hasProfile === undefined) hasProfile = true;
        }
      } catch (e) {
        // ignore
      }
      if (hasProfile === undefined) hasProfile = false;
      const apiBaseUrl = this.props.apiBaseUrl || import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

      return (
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          width: "100vw",
          padding: "24px",
          backgroundColor: "#1c2434",
          color: "#fff",
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          boxSizing: "border-box",
          textAlign: "center"
        }}>
          <div style={{
            width: "80px",
            height: "80px",
            borderRadius: "50%",
            backgroundColor: "rgba(255, 77, 77, 0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: "16px"
          }}>
            <span style={{ fontSize: "40px" }}>⚠️</span>
          </div>
          <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px" }}>
            {t("error.critical_title", locale)}
          </h2>
          <p style={{ fontSize: "14px", color: "#a0aec0", maxWidth: "320px", lineHeight: "1.4", margin: "0 0 24px 0" }}>
            {t("error.critical_desc", locale)}
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "12px", width: "100%", maxWidth: "260px" }}>
            <button
              onClick={this.handleReload}
              style={{
                padding: "12px 24px",
                backgroundColor: "#5288c1",
                color: "#fff",
                border: "none",
                borderRadius: "8px",
                fontWeight: 600,
                fontSize: "14px",
                cursor: "pointer",
              }}
            >
              {t("common.reload", locale)}
            </button>
             <button
              onClick={this.handleRetryAuth}
              style={{
                padding: "12px 24px",
                backgroundColor: "rgba(255, 255, 255, 0.05)",
                color: "#fff",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "8px",
                fontWeight: 600,
                fontSize: "14px",
                cursor: "pointer",
              }}
            >
              {t("common.retry_auth", locale)}
            </button>
            <button
              onClick={this.handleCopyReport}
              style={{
                padding: "12px 24px",
                backgroundColor: "rgba(82, 136, 193, 0.15)",
                color: "rgb(112, 172, 237)",
                border: "1px dashed rgba(82, 136, 193, 0.3)",
                borderRadius: "8px",
                fontWeight: 600,
                fontSize: "14px",
                cursor: "pointer",
                marginTop: "4px"
              }}
            >
              {this.state.copied ? t("common.copied", locale) : t("common.copy_error_report", locale)}
            </button>
          </div>

          {/* Safe Diagnostics Panel */}
          {isDev && (
            <div style={{
              marginTop: "32px",
              textAlign: "left",
              width: "100%",
              maxWidth: "480px",
              maxHeight: "300px",
              overflowY: "auto",
              fontFamily: "monospace",
              fontSize: "11px",
              backgroundColor: "rgba(0, 0, 0, 0.3)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "6px",
              padding: "12px",
              color: "#ff7b72",
            }}>
              <div style={{ fontWeight: 700, marginBottom: "8px", color: "#5288c1" }}>DEV DIAGNOSTICS (ErrorBoundary)</div>
              <div style={{ color: "#fff", marginBottom: "4px" }}>Error: {sanitizeMessage(this.state.error?.toString())}</div>
              <div>Route: {window.location.pathname}</div>
              <div>Role: {cachedRole || "N/A"}</div>
              <div>Locale: {locale || "N/A"}</div>
              <div>Profile Exists: {hasProfile ? "Yes" : "No"}</div>
              <div>API Base: {sanitizeMessage(apiBaseUrl)}</div>
              {this.state.errorInfo && (
                <pre style={{ margin: "8px 0 0 0", whiteSpace: "pre-wrap", color: "#8b949e" }}>
                  {sanitizeMessage(this.state.errorInfo.componentStack)}
                </pre>
              )}
            </div>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
export default ErrorBoundary;
