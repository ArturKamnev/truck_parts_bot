import React, { useEffect, useState } from "react";
import { getTelegramWebApp, getMockInitData, waitForTelegramLaunchContext } from "../telegram/webapp";
import { authenticateTelegram, getMe, updateLanguage } from "../api/auth";
import { type UserProfile } from "../api/auth";
import { clearStoredToken, getStoredToken, setStoredToken, onAuthError, type ApiError } from "../api/client";
import { createCustomerTicket } from "../api/tickets";
import { MessageSquare, PlusCircle, Sparkles, User, Inbox, CheckCircle2, Users, BarChart3, MoreHorizontal, Radio, Cpu, ExternalLink } from "lucide-react";
import { t } from "../i18n";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { getInitials } from "../utils/normalization";


// Import Pages & Shell Components
import { LoadingPage, type DiagnosticsData } from "../pages/LoadingPage";
import { TopBar } from "../components/TopBar";
import { CustomerHomePage } from "../pages/CustomerHomePage";
import { ManagerDashboardPage } from "../pages/ManagerDashboardPage";
import { OwnerDashboardPage } from "../pages/OwnerDashboardPage";
import { TicketChatPage } from "../pages/TicketChatPage";
import { AIChatPage } from "../pages/AIChatPage";
import { SelfTestPage } from "../pages/SelfTestPage";
import { BroadcastsPage } from "../pages/BroadcastsPage";


// --- Inline Subcomponents for Navigation ---
const NewChatView: React.FC<{ 
  onSelectTicket: (id: number) => void; 
  setActiveTab: (tab: string) => void;
  locale: string;
}> = ({ onSelectTicket, setActiveTab, locale }) => {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || sending) return;
    setSending(true);
    setError(null);
    try {
      const ticket = await createCustomerTicket(text);
      onSelectTicket(ticket.id);
      setActiveTab("chats");
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.message || t("error.create_ticket_failed", locale));
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "16px", height: "100%", overflowY: "auto" }}>
      <div>
        <h2 style={{ fontSize: "18px", fontWeight: 800, margin: "0 0 6px 0", color: "#fff" }}>
          {t("new_chat.title", locale)}
        </h2>
        <p style={{ fontSize: "13px", color: "hsl(var(--text-hint-hsl))", margin: 0 }}>
          {t("new_chat.desc", locale)}
        </p>
      </div>

      {error && (
        <div style={{ backgroundColor: "rgba(255, 77, 77, 0.1)", border: "1px solid #ff4d4d", borderRadius: "8px", padding: "12px", color: "#ff4d4d", fontSize: "13px" }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px", flex: 1 }}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={sending}
          placeholder={t("new_chat.placeholder", locale)}
          style={{
            width: "100%",
            height: "150px",
            padding: "12px",
            borderRadius: "8px",
            backgroundColor: "hsl(var(--card-bg-hsl))",
            border: "1px solid hsl(var(--border-hsl))",
            color: "#fff",
            fontSize: "14px",
            outline: "none",
            resize: "none",
          }}
        />
        <button
          type="submit"
          disabled={sending || !text.trim()}
          style={{
            padding: "12px",
            backgroundColor: "hsl(var(--accent-hsl))",
            color: "#fff",
            border: "none",
            borderRadius: "8px",
            fontWeight: 600,
            fontSize: "14px",
            cursor: "pointer",
            opacity: sending || !text.trim() ? 0.5 : 1,
            marginTop: "auto",
          }}
        >
          {sending ? t("new_chat.sending", locale) : t("new_chat.submit", locale)}
        </button>
      </form>
    </div>
  );
};

import { 
  toggleBroadcastSettings, 
  getManagerPersonalStats, 
  getActiveModel, 
  switchActiveModel, 
  getOwnerBroadcasts,
  type Broadcast,
  type ActiveModelInfo
} from "../api/tickets";

const ProfileView: React.FC<{ 
  profile: UserProfile; 
  onLogout: () => void; 
  isMockActive: boolean;
  locale: string;
  setLocale: (locale: string) => void;
  setCurrentTab?: (tab: string) => void;
  setProfile?: React.Dispatch<React.SetStateAction<UserProfile | null>>;
}> = ({ profile, onLogout, isMockActive, locale, setLocale, setCurrentTab, setProfile }) => {
  const displayName = profile.display_name;
  const initial = getInitials(displayName);
  const lang = locale || profile.preferred_language || "ru";

  // States for manager
  const [mgrStats, setMgrStats] = useState<{ tickets_claimed: number; tickets_closed: number } | null>(null);
  const [loadingMgrStats, setLoadingMgrStats] = useState(false);

  // States for owner
  const [modelInfo, setModelInfo] = useState<ActiveModelInfo | null>(null);
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([]);
  const [loadingOwnerData, setLoadingOwnerData] = useState(false);
  const [switchingModel, setSwitchingModel] = useState<string | null>(null);

  // States for customer
  const [broadcastsEnabled, setBroadcastsEnabled] = useState(profile.broadcasts_enabled);
  const [togglingBroadcasts, setTogglingBroadcasts] = useState(false);
  const [savingLanguage, setSavingLanguage] = useState(false);

  useEffect(() => {
    if (profile.role === "manager") {
      setLoadingMgrStats(true);
      getManagerPersonalStats()
        .then(setMgrStats)
        .catch(console.error)
        .finally(() => setLoadingMgrStats(false));
    } else if (profile.role === "owner" || profile.role === "co_owner") {
      setLoadingOwnerData(true);
      Promise.all([
        profile.role === "owner" ? getActiveModel() : Promise.resolve(null),
        getOwnerBroadcasts(),
      ])
        .then(([modelData, broadcastData]) => {
          if (modelData) setModelInfo(modelData);
          setBroadcasts(broadcastData);
        })
        .catch(console.error)
        .finally(() => setLoadingOwnerData(false));
    }
  }, [profile.role]);

  const handleToggleBroadcast = async () => {
    if (togglingBroadcasts) return;
    setTogglingBroadcasts(true);
    const nextVal = !broadcastsEnabled;
    try {
      const result = await toggleBroadcastSettings(nextVal);
      setBroadcastsEnabled(result);
      if (setProfile) {
        setProfile(prev => prev ? { ...prev, broadcasts_enabled: result } : null);
        // Also update local storage cache
        const cached = localStorage.getItem("tma_user_profile");
        if (cached) {
          try {
            const p = JSON.parse(cached);
            p.broadcasts_enabled = result;
            localStorage.setItem("tma_user_profile", JSON.stringify(p));
          } catch(e){}
        }
      }
    } catch (e) {
      console.error(e);
      alert(t("profile.broadcast_toggle_error", lang));
    } finally {
      setTogglingBroadcasts(false);
    }
  };

  const handleLanguageChange = async (language: "ru" | "en" | "ky") => {
    if (savingLanguage) return;
    const previousLanguage = profile?.preferred_language || "ru";
    setSavingLanguage(true);
    try {
      const savedLanguage = await updateLanguage(language);
      setLocale(savedLanguage);
      localStorage.setItem("tma_preferred_language", savedLanguage);
      
      if (setProfile) {
        setProfile(prev => {
          const next = prev ? { ...prev, preferred_language: savedLanguage } : prev;
          if (next) localStorage.setItem("tma_user_profile", JSON.stringify(next));
          return next;
        });
      }
      
      const freshProfile = await getMe();
      if (setProfile) {
        setProfile(freshProfile);
      }
      localStorage.setItem("tma_user_profile", JSON.stringify(freshProfile));
      setLocale(freshProfile.preferred_language || savedLanguage);
      const finalLanguage = freshProfile.preferred_language || "ru";

      if (import.meta.env.DEV) {
        console.log("[Language Switch Success]", {
          selectedLanguage: language,
          previousLanguage,
          apiStatus: "SUCCESS",
          returnedLanguage: finalLanguage,
        });
      }
    } catch (e) {
      console.error("[Language Switch Failure]", e);
      const apiErr = e as ApiError;
      
      if (import.meta.env.DEV) {
        console.log("[Language Switch Failure Dev Info]", {
          selectedLanguage: language,
          previousLanguage,
          apiStatus: "FAILED",
          error: apiErr.message,
        });
      }
      
      setLocale(previousLanguage);
      alert(t("error.language_update_failed", previousLanguage));
    } finally {
      setSavingLanguage(false);
    }
  };

  const handleModelChange = async (modelId: string) => {
    if (switchingModel) return;
    setSwitchingModel(modelId);
    try {
      const active = await switchActiveModel(modelId);
      setModelInfo(prev => prev ? { ...prev, active_model: active } : null);
    } catch (e) {
      console.error(e);
      alert(`${t("profile.model_switch_failed", lang)}: ${(e as ApiError).message || t("common.error", lang)}`);
    } finally {
      setSwitchingModel(null);
    }
  };

  const botChatUrl = profile.miniapp_url
    ? profile.miniapp_url.replace(/\/app(\?.*)?$/, "")
    : "https://t.me/your_bot";

  const handleOpenBot = () => {
    const webApp = getTelegramWebApp();
    if (webApp) {
      webApp.openTelegramLink(botChatUrl);
    } else {
      window.open(botChatUrl, "_blank");
    }
  };

  return (
    <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "16px", height: "100%", overflowY: "auto", paddingBottom: "100px" }}>
      <div style={{ textAlign: "center", padding: "12px 0" }}>
        <div
          style={{
            width: "56px",
            height: "56px",
            borderRadius: "50%",
            backgroundColor: "rgba(82, 136, 193, 0.15)",
            color: "hsl(var(--accent-hsl))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "20px",
            fontWeight: 700,
            margin: "0 auto 8px auto",
          }}
        >
          {initial}
        </div>
        <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: "0 0 2px 0" }}>{displayName}</h3>
        <span style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>@{profile.username || t("common.no_username", lang)}</span>
      </div>

      {/* Role and System Info */}
      <div
        style={{
          backgroundColor: "hsl(var(--card-bg-hsl))",
          border: "1px solid hsl(var(--border-hsl))",
          borderRadius: "8px",
          padding: "12px 16px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
          <span style={{ color: "hsl(var(--text-hint-hsl))" }}>{t("profile.telegram_id", lang)}:</span>
          <span style={{ fontWeight: 600, color: "#fff" }}>{profile.telegram_user_id}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
          <span style={{ color: "hsl(var(--text-hint-hsl))" }}>{t("profile.role", lang)}:</span>
          <span style={{ fontWeight: 700, color: "hsl(var(--accent-hsl))", textTransform: "uppercase" }}>{profile.role}</span>
        </div>
        {isMockActive && (
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
            <span style={{ color: "hsl(var(--warning-hsl))" }}>{t("profile.mode", lang)}:</span>
            <span style={{ fontWeight: 700, color: "hsl(var(--warning-hsl))" }}>{t("profile.mock_demo", lang)}</span>
          </div>
        )}
      </div>

      <div
        style={{
          backgroundColor: "hsl(var(--card-bg-hsl))",
          border: "1px solid hsl(var(--border-hsl))",
          borderRadius: "8px",
          padding: "12px 16px",
          display: "flex",
          flexDirection: "column",
          gap: "10px",
        }}
      >
        <span style={{ color: "hsl(var(--text-hint-hsl))", fontSize: "12px", fontWeight: 700 }}>
          {t("profile.language", lang)}
        </span>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px" }}>
          {([
            ["ru", "RU"],
            ["en", "EN"],
            ["ky", "KY"],
          ] as const).map(([code, label]) => {
            const active = lang === code;
            return (
              <button
                key={code}
                onClick={() => handleLanguageChange(code)}
                disabled={savingLanguage}
                style={{
                  padding: "9px 0",
                  borderRadius: "8px",
                  border: active ? "1px solid hsl(var(--accent-hsl))" : "1px solid hsl(var(--border-hsl))",
                  backgroundColor: active ? "rgba(82, 136, 193, 0.16)" : "rgba(255,255,255,0.03)",
                  color: active ? "hsl(var(--accent-hsl))" : "#fff",
                  fontWeight: 700,
                  fontSize: "12px",
                  cursor: savingLanguage ? "wait" : "pointer",
                }}
              >
                {savingLanguage && active ? "..." : label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Customer controls */}
      {profile.role === "customer" && (
        <>
          <div
            style={{
              backgroundColor: "hsl(var(--card-bg-hsl))",
              border: "1px solid hsl(var(--border-hsl))",
              borderRadius: "8px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            <h4 style={{ margin: "0 0 4px 0", fontSize: "14px", fontWeight: 700, color: "#fff" }}>
              {t("profile.notifications", lang)}
            </h4>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                <span style={{ fontSize: "13px", color: "#fff" }}>{t("profile.receive_broadcasts", lang)}</span>
                <span style={{ fontSize: "11px", color: "hsl(var(--text-hint-hsl))" }}>
                  {t("profile.receive_broadcasts_desc", lang)}
                </span>
              </div>
              <label className="switch" style={{ position: "relative", display: "inline-block", width: "40px", height: "20px" }}>
                <input
                  type="checkbox"
                  checked={broadcastsEnabled}
                  onChange={handleToggleBroadcast}
                  disabled={togglingBroadcasts}
                  style={{ opacity: 0, width: 0, height: 0 }}
                />
                <span
                  style={{
                    position: "absolute",
                    cursor: "pointer",
                    top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: broadcastsEnabled ? "hsl(var(--success-hsl))" : "#444",
                    transition: "0.2s",
                    borderRadius: "20px",
                  }}
                >
                  <span
                    style={{
                      position: "absolute",
                      content: '""',
                      height: "14px", width: "14px",
                      left: broadcastsEnabled ? "22px" : "3px",
                      bottom: "3px",
                      backgroundColor: "white",
                      transition: "0.2s",
                      borderRadius: "50%",
                    }}
                  />
                </span>
              </label>
            </div>
          </div>

          <button
            onClick={handleOpenBot}
            style={{
              width: "100%",
              padding: "12px",
              backgroundColor: "hsl(var(--accent-hsl))",
              color: "#fff",
              border: "none",
              borderRadius: "8px",
              fontWeight: 600,
              fontSize: "14px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
            }}
          >
            <ExternalLink size={16} />
            {t("common.telegram_bot", lang)}
          </button>
        </>
      )}

      {/* Manager controls */}
      {profile.role === "manager" && (
        <div
          style={{
            backgroundColor: "hsl(var(--card-bg-hsl))",
            border: "1px solid hsl(var(--border-hsl))",
            borderRadius: "8px",
            padding: "16px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          <h4 style={{ margin: "0 0 4px 0", fontSize: "14px", fontWeight: 700, color: "#fff" }}>
            {t("profile.stats", lang)}
          </h4>
          {loadingMgrStats ? (
            <div className="skeleton" style={{ height: "40px", borderRadius: "4px" }} />
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div style={{ backgroundColor: "rgba(255,255,255,0.03)", padding: "10px", borderRadius: "6px", textAlign: "center", border: "1px solid hsl(var(--border-hsl))" }}>
                <span style={{ display: "block", fontSize: "11px", color: "hsl(var(--text-hint-hsl))", marginBottom: "4px" }}>
                  {t("profile.stats_claimed", lang)}
                </span>
                <span style={{ fontSize: "18px", fontWeight: 700, color: "hsl(var(--accent-hsl))" }}>{mgrStats?.tickets_claimed ?? 0}</span>
              </div>
              <div style={{ backgroundColor: "rgba(255,255,255,0.03)", padding: "10px", borderRadius: "6px", textAlign: "center", border: "1px solid hsl(var(--border-hsl))" }}>
                <span style={{ display: "block", fontSize: "11px", color: "hsl(var(--text-hint-hsl))", marginBottom: "4px" }}>
                  {t("profile.stats_closed", lang)}
                </span>
                <span style={{ fontSize: "18px", fontWeight: 700, color: "hsl(var(--success-hsl))" }}>{mgrStats?.tickets_closed ?? 0}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Owner controls */}
      {(profile.role === "owner" || profile.role === "co_owner") && (
        <>
          {/* Shortcuts */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <button
              onClick={() => setCurrentTab && setCurrentTab("managers")}
              style={{
                padding: "10px",
                backgroundColor: "hsl(var(--card-bg-hsl))",
                border: "1px solid hsl(var(--border-hsl))",
                borderRadius: "8px",
                color: "#fff",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <Users size={16} style={{ color: "hsl(var(--accent-hsl))" }} />
              {t("nav.managers", lang)}
            </button>
            <button
              onClick={() => setCurrentTab && setCurrentTab("stats")}
              style={{
                padding: "10px",
                backgroundColor: "hsl(var(--card-bg-hsl))",
                border: "1px solid hsl(var(--border-hsl))",
                borderRadius: "8px",
                color: "#fff",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <BarChart3 size={16} style={{ color: "hsl(var(--success-hsl))" }} />
              {t("nav.stats", lang)}
            </button>
          </div>

          {/* AI Settings */}
          {profile.role === "owner" && <div
            style={{
              backgroundColor: "hsl(var(--card-bg-hsl))",
              border: "1px solid hsl(var(--border-hsl))",
              borderRadius: "8px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <Cpu size={16} style={{ color: "hsl(var(--accent-hsl))" }} />
              <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff" }}>
                {t("profile.ai_settings", lang)}
              </h4>
            </div>
            
            {loadingOwnerData && !modelInfo ? (
              <div className="skeleton" style={{ height: "60px", borderRadius: "6px" }} />
            ) : modelInfo ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {Object.entries(modelInfo.available_models).map(([id, label]) => {
                  const isActive = modelInfo.active_model === id;
                  const isPending = switchingModel === id;
                  return (
                    <label
                      key={id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        padding: "10px",
                        borderRadius: "6px",
                        backgroundColor: isActive ? "rgba(82, 136, 193, 0.08)" : "rgba(255,255,255,0.02)",
                        border: isActive ? "1px solid hsl(var(--accent-hsl))" : "1px solid hsl(var(--border-hsl))",
                        cursor: "pointer",
                        fontSize: "13px",
                      }}
                    >
                      <input
                        type="radio"
                        name="activeModel"
                        checked={isActive}
                        disabled={switchingModel !== null}
                        onChange={() => handleModelChange(id)}
                        style={{ margin: 0 }}
                      />
                      <span style={{ color: isActive ? "#fff" : "hsl(var(--text-hint-hsl))", flex: 1 }}>
                        {label} {isPending && "..."}
                      </span>
                    </label>
                  );
                })}
              </div>
            ) : (
              <span style={{ fontSize: "12px", color: "hsl(var(--error-hsl))" }}>{t("profile.model_load_failed", lang)}</span>
            )}
          </div>}

          {/* Broadcasts History */}
          <div
            style={{
              backgroundColor: "hsl(var(--card-bg-hsl))",
              border: "1px solid hsl(var(--border-hsl))",
              borderRadius: "8px",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <Radio size={16} style={{ color: "hsl(var(--accent-hsl))" }} />
              <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff" }}>
                {t("profile.broadcast_history", lang)}
              </h4>
            </div>

            <div
              style={{
                backgroundColor: "rgba(82, 136, 193, 0.05)",
                border: "1px dashed rgba(82, 136, 193, 0.2)",
                borderRadius: "6px",
                padding: "10px",
                fontSize: "11px",
                color: "hsl(var(--text-hint-hsl))",
                lineHeight: "1.4",
              }}
            >
              {t("profile.broadcast_hint", lang)}
            </div>

            {loadingOwnerData && broadcasts.length === 0 ? (
              <div className="skeleton" style={{ height: "80px", borderRadius: "6px" }} />
            ) : broadcasts.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "250px", overflowY: "auto" }}>
                {broadcasts.map((b) => (
                  <div
                    key={b.id}
                    style={{
                      padding: "10px",
                      borderRadius: "6px",
                      backgroundColor: "rgba(255,255,255,0.02)",
                      border: "1px solid hsl(var(--border-hsl))",
                      display: "flex",
                      flexDirection: "column",
                      gap: "4px",
                      fontSize: "12px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontWeight: 600 }}>
                      <span style={{ color: "hsl(var(--accent-hsl))" }}>{t("broadcast.item_title", lang).replace("{id}", String(b.id))}</span>
                      <span
                        style={{
                          fontSize: "10px",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          backgroundColor:
                            b.status === "completed" ? "rgba(46, 204, 113, 0.15)" :
                            b.status === "sending" ? "rgba(52, 152, 219, 0.15)" :
                            "rgba(255, 255, 255, 0.05)",
                          color:
                            b.status === "completed" ? "hsl(var(--success-hsl))" :
                            b.status === "sending" ? "hsl(var(--accent-hsl))" :
                            "hsl(var(--text-hint-hsl))",
                          textTransform: "uppercase",
                        }}
                      >
                        {b.status}
                      </span>
                    </div>
                    {b.content_preview && (
                      <span style={{ color: "hsl(var(--text-hint-hsl))", fontSize: "11px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {b.content_preview}
                      </span>
                    )}
                    <div style={{ display: "flex", gap: "10px", fontSize: "10px", color: "hsl(var(--text-hint-hsl))", marginTop: "2px" }}>
                      <span>{t("broadcast.recipients", lang)}: <b>{b.recipient_count}</b></span>
                      <span>{t("broadcast.delivered", lang)}: <b style={{ color: "hsl(var(--success-hsl))" }}>{b.delivered_count}</b></span>
                      {b.failed_count > 0 && <span>{t("broadcast.failed", lang)}: <b style={{ color: "hsl(var(--error-hsl))" }}>{b.failed_count}</b></span>}
                      {b.blocked_count > 0 && <span>{t("broadcast.blocked", lang)}: <b style={{ color: "hsl(var(--warning-hsl))" }}>{b.blocked_count}</b></span>}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <span style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>
                {t("broadcast.empty", lang)}
              </span>
            )}
          </div>
        </>
      )}

      {/* Logout button */}
      <button
        onClick={onLogout}
        style={{
          padding: "10px",
          backgroundColor: "rgba(255, 77, 77, 0.08)",
          color: "#ff4d4d",
          border: "1px solid rgba(255, 77, 77, 0.15)",
          borderRadius: "8px",
          fontWeight: 600,
          fontSize: "13px",
          cursor: "pointer",
          marginTop: "12px",
        }}
      >
        {t("common.logout", lang)}
      </button>
    </div>
  );
};


type AuthState =
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

export const App: React.FC = () => {
  const [profile, setProfile] = useState<UserProfile | null>(() => {
    const cached = localStorage.getItem("tma_user_profile");
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (parsed && ["customer", "manager", "owner", "co_owner"].includes(parsed.role)) {
          return parsed;
        }
      } catch (e) {
        localStorage.removeItem("tma_user_profile");
      }
    }
    return null;
  });
  const [authState, setAuthState] = useState<AuthState>("booting");
  const [error, setError] = useState<ApiError | null>(null);
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null);
  const [isMockActive, setIsMockActive] = useState(false);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsData | null>(null);
  const [currentTab, setCurrentTab] = useState<string>("");
  const [locale, setLocale] = useState<string>(() => {
    const cachedLocale = localStorage.getItem("tma_preferred_language");
    if (cachedLocale && ["ru", "en", "ky"].includes(cachedLocale)) return cachedLocale;
    const cached = localStorage.getItem("tma_user_profile");
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (["ru", "en", "ky"].includes(parsed?.preferred_language)) {
          return parsed.preferred_language;
        }
      } catch (e) {
        localStorage.removeItem("tma_user_profile");
      }
    }
    return "ru";
  });

  useEffect(() => {
    if (profile) {
      if (profile.role === "customer") {
        setCurrentTab("chats");
      } else if (profile.role === "manager") {
        setCurrentTab("active");
      } else if (profile.role === "owner" || profile.role === "co_owner") {
        setCurrentTab("overview");
      }
    }
  }, [profile?.role]);

  const isDev = import.meta.env.DEV;
  const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

  const handleAuthentication = async (initData: string, fromMock = false, currentDiagnostics: DiagnosticsData) => {
    currentDiagnostics.authAttempted = true;
    setDiagnostics({ ...currentDiagnostics });
    try {
      setError(null);
      const authData = await authenticateTelegram(initData);
      setStoredToken(authData.token);
      setProfile(authData.profile);
      setLocale(authData.profile.preferred_language || "ru");
      localStorage.setItem("tma_user_profile", JSON.stringify(authData.profile));
      localStorage.setItem("tma_preferred_language", authData.profile.preferred_language || "ru");
      setIsMockActive(fromMock);
      
      currentDiagnostics.currentRole = authData.profile.role;
      currentDiagnostics.currentLocale = authData.profile.preferred_language;
      currentDiagnostics.errorStatus = 200;
      currentDiagnostics.errorType = "OK";
      setDiagnostics({ ...currentDiagnostics });

      if (["customer", "manager", "owner", "co_owner"].includes(authData.profile.role)) {
        setAuthState("ready");
      } else {
        setAuthState("unsupportedRole");
      }
    } catch (err) {
      const apiErr = err as ApiError;
      currentDiagnostics.errorStatus = apiErr.status;
      currentDiagnostics.errorType = apiErr.message || "Authentication Failed";
      setDiagnostics({ ...currentDiagnostics });

      let errMsg = t("error.connection_failure", locale);
      if (apiErr.status === 401 || apiErr.status === 403) {
        errMsg = t("error.stale_session", locale);
        setAuthState("invalidSession");
      } else {
        setAuthState("apiUnavailable");
      }

      setError({
        status: apiErr.status,
        message: errMsg,
      });
      clearStoredToken();
      localStorage.removeItem("tma_user_profile");
      setProfile(null);
    }
  };

  const refreshProfile = async (token?: string, placeholderProfile?: UserProfile | null, currentDiagnostics?: DiagnosticsData | null) => {
    const activeToken = token || getStoredToken();
    if (!activeToken) return;
    try {
      const freshProfile = await getMe();
      if (currentDiagnostics) {
        currentDiagnostics.currentRole = freshProfile.role;
        currentDiagnostics.currentLocale = freshProfile.preferred_language;
        setDiagnostics({ ...currentDiagnostics });
      }

      setProfile(freshProfile);
      setLocale(freshProfile.preferred_language || locale);
      localStorage.setItem("tma_user_profile", JSON.stringify(freshProfile));
      localStorage.setItem("tma_preferred_language", freshProfile.preferred_language || locale);
      setIsMockActive(activeToken.includes(".mock_") || !window.Telegram?.WebApp?.initData);
      setError(null);

      if (["customer", "manager", "owner", "co_owner"].includes(freshProfile.role)) {
        setAuthState("ready");
      } else {
        setAuthState("unsupportedRole");
      }
    } catch (err) {
      const apiErr = err as ApiError;
      if (currentDiagnostics) {
        currentDiagnostics.errorStatus = apiErr.status;
        currentDiagnostics.errorType = apiErr.message || "Profile fetch failed";
        setDiagnostics({ ...currentDiagnostics });
      }

      if (apiErr.status === 401 || apiErr.status === 403) {
        clearStoredToken();
        localStorage.removeItem("tma_user_profile");
        setProfile(null);
        setError({
          status: apiErr.status,
          message: t("error.stale_session", locale),
        });
        setAuthState("invalidSession");
      } else {
        if (!placeholderProfile) {
          setAuthState("apiUnavailable");
          setError(apiErr);
        }
      }
    }
  };

  const initializeApp = async (forceFreshAuth = false) => {
    setError(null);
    setAuthState("booting");

    if (forceFreshAuth) {
      clearStoredToken();
      localStorage.removeItem("tma_user_profile");
      setProfile(null);
      setIsMockActive(false);
    }

    setAuthState("waitingTelegram");
    const { webApp, initData } = await waitForTelegramLaunchContext();

    const hasTg = typeof window !== "undefined" && !!window.Telegram;
    const hasWebApp = !!webApp;
    const initDataLen = initData.length;

    const storedToken = forceFreshAuth ? null : getStoredToken();
    const cachedProfileStr = localStorage.getItem("tma_user_profile");
    let cachedProfile: UserProfile | null = null;
    if (cachedProfileStr) {
      try {
        const parsed = JSON.parse(cachedProfileStr);
        if (parsed && ["customer", "manager", "owner", "co_owner"].includes(parsed.role)) {
          cachedProfile = parsed;
        } else {
          localStorage.removeItem("tma_user_profile");
        }
      } catch (e) {
        localStorage.removeItem("tma_user_profile");
      }
    }

    const currentDiagnostics: DiagnosticsData = {
      apiBaseUrl,
      telegramExists: hasTg,
      webAppExists: hasWebApp,
      platform: (webApp?.initDataUnsafe as any)?.platform || (webApp as any)?.platform || null,
      initDataLength: initDataLen,
      authAttempted: false,
      errorStatus: null,
      errorType: null,
      currentRoute: window.location.pathname,
      currentRole: cachedProfile?.role || null,
      currentLocale: cachedProfile?.preferred_language || null,
    };
    setDiagnostics(currentDiagnostics);

    if (initData) {
      setAuthState("authenticating");
      await handleAuthentication(initData, false, currentDiagnostics);
    } else if (storedToken && isDev) {
      if (cachedProfile) {
        setProfile(cachedProfile);
        setLocale(cachedProfile.preferred_language || locale);
        setAuthState("ready");
        refreshProfile(storedToken, cachedProfile, currentDiagnostics);
      } else {
        setAuthState("loadingProfile");
        await refreshProfile(storedToken, null, currentDiagnostics);
      }
    } else {
      localStorage.removeItem("tma_user_profile");
      setProfile(null);
      if (isDev) {
        setAuthState("missingInitData");
      } else {
        setError({
          status: 403,
          message: t("error.restricted_access_desc", locale),
        });
        setAuthState("missingInitData");
      }
    }
  };

  useEffect(() => {
    initializeApp();

    const unsubscribe = onAuthError(() => {
      setProfile(null);
      setSelectedTicketId(null);
      setIsMockActive(false);
      localStorage.removeItem("tma_user_profile");
      setError({
        status: 401,
        message: t("error.stale_session", locale),
      });
      setAuthState("invalidSession");
    });

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible" && authState === "ready") {
        refreshProfile(undefined, profile, diagnostics);
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    const handleGlobalError = (event: ErrorEvent) => {
      setAuthState("fatalRenderError");
      setError({
        status: 500,
        message: event.message || "Global runtime error",
      });
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      setAuthState("fatalRenderError");
      setError({
        status: 500,
        message: event.reason?.message || String(event.reason) || "Unhandled promise rejection",
      });
    };

    window.addEventListener("error", handleGlobalError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);

    return () => {
      unsubscribe();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("error", handleGlobalError);
      window.removeEventListener("unhandledrejection", handleUnhandledRejection);
    };
  }, []);

  useEffect(() => {
    if (profile && authState === "ready") {
      refreshProfile(undefined, profile, diagnostics);
    }
  }, [currentTab]);

  const handleSelectMockRole = async (role: "customer" | "manager" | "owner" | "co_owner") => {
    const mockInitData = getMockInitData(role);
    const mockDiagnostics = diagnostics || {
      apiBaseUrl,
      telegramExists: false,
      webAppExists: false,
      platform: "mock",
      initDataLength: mockInitData.length,
      authAttempted: false,
      errorStatus: null,
      errorType: null,
    };
    await handleAuthentication(mockInitData, true, mockDiagnostics);
  };

  const handleLogout = () => {
    clearStoredToken();
    localStorage.removeItem("tma_user_profile");
    setProfile(null);
    setSelectedTicketId(null);
    setIsMockActive(false);
    setError(null);
    initializeApp(true);
  };

  const isTestMode = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("test") === "true";
  if (isTestMode) {
    return <SelfTestPage />;
  }

  // --- Rendering Routing Switcher ---
  if (authState !== "ready" || !profile) {
    return (
      <ErrorBoundary
        role={profile?.role}
        locale={locale}
        hasProfile={!!profile}
        apiBaseUrl={apiBaseUrl}
      >
        <LoadingPage
          authState={authState}
          error={error}
          onRetry={() => initializeApp(true)}
          isDev={isDev}
          onSelectMockRole={handleSelectMockRole}
          diagnostics={diagnostics}
          locale={locale}
        />
      </ErrorBoundary>
    );
  }

  // Active chat page view
  if (selectedTicketId !== null) {
    return (
      <ErrorBoundary
        role={profile.role}
        locale={locale}
        hasProfile={true}
        apiBaseUrl={apiBaseUrl}
      >
        <TicketChatPage
          ticketId={selectedTicketId}
          viewerRole={profile.role}
          onBack={() => setSelectedTicketId(null)}
          locale={locale}
        />
      </ErrorBoundary>
    );
  }

  // Main layouts
  return (
    <ErrorBoundary
      role={profile.role}
      locale={locale}
      hasProfile={true}
      apiBaseUrl={apiBaseUrl}
    >
      <div style={{ display: "flex", flexDirection: "column", height: "100%", width: "100%" }}>
        <TopBar profile={profile} isMockActive={isMockActive} onLogout={handleLogout} locale={locale} />
        
        <main style={{ flex: 1, overflow: "hidden" }}>
          {profile.role === "customer" && (
            <>
              {currentTab === "chats" && <CustomerHomePage onSelectTicket={setSelectedTicketId} locale={locale} setActiveTab={setCurrentTab} />}
              {currentTab === "new_chat" && (
                <NewChatView 
                  onSelectTicket={setSelectedTicketId} 
                  setActiveTab={setCurrentTab} 
                  locale={locale}
                />
              )}
              {currentTab === "ai_helper" && <AIChatPage locale={locale} />}
              {currentTab === "profile" && (
                <ProfileView 
                  profile={profile} 
                  onLogout={handleLogout} 
                  isMockActive={isMockActive} 
                  locale={locale}
                  setLocale={setLocale}
                  setCurrentTab={setCurrentTab}
                  setProfile={setProfile}
                />
              )}
            </>
          )}
          {profile.role === "manager" && (
            <>
              {(currentTab === "new" || currentTab === "active" || currentTab === "closed") && (
                <ManagerDashboardPage 
                  onSelectTicket={setSelectedTicketId} 
                  activeTab={currentTab as any} 
                  setActiveTab={setCurrentTab as any} 
                  locale={locale}
                />
              )}
              {currentTab === "ai_helper" && <AIChatPage locale={locale} />}
              {currentTab === "profile" && (
                <ProfileView 
                  profile={profile} 
                  onLogout={handleLogout} 
                  isMockActive={isMockActive} 
                  locale={locale}
                  setLocale={setLocale}
                  setCurrentTab={setCurrentTab}
                  setProfile={setProfile}
                />
              )}
            </>
          )}
          {(profile.role === "owner" || profile.role === "co_owner") && (
            <>
              {(currentTab === "overview" || currentTab === "managers" || currentTab === "stats") && (
                <OwnerDashboardPage 
                  onSelectTicket={setSelectedTicketId} 
                  activeTab={currentTab === "overview" ? "dashboard" : currentTab as any} 
                  setActiveTab={(tab) => setCurrentTab(tab === "dashboard" ? "overview" : tab)} 
                  locale={locale}
                />
              )}
              {currentTab === "broadcasts" && <BroadcastsPage locale={locale} />}
              {currentTab === "ai_helper" && <AIChatPage locale={locale} />}
              {currentTab === "more" && (
                <ProfileView 
                  profile={profile} 
                  onLogout={handleLogout} 
                  isMockActive={isMockActive} 
                  locale={locale}
                  setLocale={setLocale}
                  setCurrentTab={setCurrentTab}
                  setProfile={setProfile}
                />
              )}
            </>
          )}
          {!["customer", "manager", "owner", "co_owner"].includes(profile.role) && (
            <div style={{ padding: "20px", color: "red", textAlign: "center" }}>
              {t("error.unsupported_role_fallback", locale)}
            </div>
          )}
        </main>

        {/* Bottom Navigation Tabs */}
        <div
          style={{
            display: "flex",
            backgroundColor: "hsl(var(--card-bg-hsl))",
            borderTop: "1px solid hsl(var(--border-hsl))",
            padding: "6px 8px calc(6px + var(--sab))",
            justifyContent: "space-around",
            alignItems: "center",
            zIndex: 10,
          }}
        >
          {profile.role === "customer" && (
            <>
              <button
                onClick={() => setCurrentTab("chats")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "chats" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <MessageSquare size={20} />
                {t("nav.chats", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("new_chat")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "new_chat" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <PlusCircle size={20} />
                {t("nav.new_chat", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("ai_helper")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "ai_helper" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <Sparkles size={20} />
                {t("nav.ai_helper", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("profile")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "profile" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <User size={20} />
                {t("nav.profile", locale)}
              </button>
            </>
          )}

          {profile.role === "manager" && (
            <>
              <button
                onClick={() => setCurrentTab("new")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "new" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <Inbox size={20} />
                {t("nav.new_queue", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("active")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "active" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <MessageSquare size={20} />
                {t("nav.active_chats", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("closed")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "closed" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <CheckCircle2 size={20} />
                {t("nav.closed_chats", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("ai_helper")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "ai_helper" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <Sparkles size={20} />
                {t("nav.ai_helper", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("profile")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "profile" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <User size={20} />
                {t("nav.profile", locale)}
              </button>
            </>
          )}

          {(profile.role === "owner" || profile.role === "co_owner") && (
            <>
              <button
                onClick={() => setCurrentTab("overview")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "overview" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <MessageSquare size={20} />
                {t("nav.overview", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("managers")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "managers" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <Users size={20} />
                {t("nav.managers", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("stats")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "stats" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <BarChart3 size={20} />
                {t("nav.stats", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("broadcasts")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "broadcasts" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <Radio size={20} />
                {t("nav.broadcasts", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("ai_helper")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "ai_helper" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <Sparkles size={20} />
                {t("nav.ai_helper", locale)}
              </button>
              <button
                onClick={() => setCurrentTab("more")}
                style={{
                  flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "2px",
                  background: "none", border: "none", color: currentTab === "more" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  fontSize: "10px", fontWeight: 600, cursor: "pointer"
                }}
              >
                <MoreHorizontal size={20} />
                {t("nav.more", locale)}
              </button>
            </>
          )}
        </div>
      </div>
    </ErrorBoundary>
  );
};

export default App;
