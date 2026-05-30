import React, { useEffect, useState } from "react";
import { getTelegramWebApp, getMockInitData, waitForTelegramLaunchContext } from "../telegram/webapp";
import { authenticateTelegram, getMe, updateLanguage } from "../api/auth";
import { type UserProfile } from "../api/auth";
import { clearStoredToken, getStoredToken, setStoredToken, onAuthError, type ApiError } from "../api/client";
import { createCustomerTicket } from "../api/tickets";
import { MessageSquare, PlusCircle, Sparkles, User, Inbox, CheckCircle2, Users, BarChart3, MoreHorizontal, Radio, Cpu, ExternalLink } from "lucide-react";

// Import Pages & Shell Components
import { LoadingPage, type DiagnosticsData } from "../pages/LoadingPage";
import { TopBar } from "../components/TopBar";
import { CustomerHomePage } from "../pages/CustomerHomePage";
import { ManagerDashboardPage } from "../pages/ManagerDashboardPage";
import { OwnerDashboardPage } from "../pages/OwnerDashboardPage";
import { TicketChatPage } from "../pages/TicketChatPage";
import { AIChatPage } from "../pages/AIChatPage";

// --- Inline Subcomponents for Navigation ---
const NewChatView: React.FC<{ onSelectTicket: (id: number) => void; setActiveTab: (tab: string) => void }> = ({ onSelectTicket, setActiveTab }) => {
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
      setError(apiErr.message || "Не удалось создать обращение. У вас может быть уже открытое обращение.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "16px", height: "100%", overflowY: "auto" }}>
      <div>
        <h2 style={{ fontSize: "18px", fontWeight: 800, margin: "0 0 6px 0", color: "#fff" }}>Новое обращение</h2>
        <p style={{ fontSize: "13px", color: "hsl(var(--text-hint-hsl))", margin: 0 }}>
          Опишите ваш вопрос или проблему. Первый свободный менеджер ответит вам.
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
          placeholder="Введите сообщение..."
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
          {sending ? "Отправка..." : "Отправить обращение"}
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
  setCurrentTab?: (tab: string) => void;
  setProfile?: React.Dispatch<React.SetStateAction<UserProfile | null>>;
}> = ({ profile, onLogout, isMockActive, setCurrentTab, setProfile }) => {
  const displayName = [profile.first_name, profile.last_name].filter(Boolean).join(" ") || profile.username || `User ${profile.telegram_user_id}`;
  
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
      alert("Не удалось изменить настройки рассылок");
    } finally {
      setTogglingBroadcasts(false);
    }
  };

  const handleLanguageChange = async (language: "ru" | "en" | "ky") => {
    if (savingLanguage) return;
    setSavingLanguage(true);
    try {
      const savedLanguage = await updateLanguage(language);
      if (setProfile) {
        setProfile(prev => {
          const next = prev ? { ...prev, preferred_language: savedLanguage } : prev;
          if (next) localStorage.setItem("tma_user_profile", JSON.stringify(next));
          return next;
        });
      }
    } catch (e) {
      console.error(e);
      alert((e as ApiError).message || "Failed to update language.");
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
      alert("Не удалось изменить активную модель: " + ((e as ApiError).message || "Ошибка"));
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
          {displayName.charAt(0).toUpperCase()}
        </div>
        <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: "0 0 2px 0" }}>{displayName}</h3>
        <span style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>@{profile.username || "no_username"}</span>
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
          <span style={{ color: "hsl(var(--text-hint-hsl))" }}>Telegram ID:</span>
          <span style={{ fontWeight: 600, color: "#fff" }}>{profile.telegram_user_id}</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
          <span style={{ color: "hsl(var(--text-hint-hsl))" }}>Роль:</span>
          <span style={{ fontWeight: 700, color: "hsl(var(--accent-hsl))", textTransform: "uppercase" }}>{profile.role}</span>
        </div>
        {isMockActive && (
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
            <span style={{ color: "hsl(var(--warning-hsl))" }}>Режим:</span>
            <span style={{ fontWeight: 700, color: "hsl(var(--warning-hsl))" }}>Mock Demo</span>
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
          Language
        </span>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px" }}>
          {([
            ["ru", "RU"],
            ["en", "EN"],
            ["ky", "KY"],
          ] as const).map(([code, label]) => {
            const active = (profile.preferred_language || "ru") === code;
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
                {label}
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
            <h4 style={{ margin: "0 0 4px 0", fontSize: "14px", fontWeight: 700, color: "#fff" }}>Настройки уведомлений</h4>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                <span style={{ fontSize: "13px", color: "#fff" }}>Получать рассылки</span>
                <span style={{ fontSize: "11px", color: "hsl(var(--text-hint-hsl))" }}>Получайте новости о наличии запчастей</span>
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
            Перейти в Telegram-бот
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
          <h4 style={{ margin: "0 0 4px 0", fontSize: "14px", fontWeight: 700, color: "#fff" }}>Личная статистика</h4>
          {loadingMgrStats ? (
            <div className="skeleton" style={{ height: "40px", borderRadius: "4px" }} />
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div style={{ backgroundColor: "rgba(255,255,255,0.03)", padding: "10px", borderRadius: "6px", textAlign: "center", border: "1px solid hsl(var(--border-hsl))" }}>
                <span style={{ display: "block", fontSize: "11px", color: "hsl(var(--text-hint-hsl))", marginBottom: "4px" }}>Взято обращений</span>
                <span style={{ fontSize: "18px", fontWeight: 700, color: "hsl(var(--accent-hsl))" }}>{mgrStats?.tickets_claimed ?? 0}</span>
              </div>
              <div style={{ backgroundColor: "rgba(255,255,255,0.03)", padding: "10px", borderRadius: "6px", textAlign: "center", border: "1px solid hsl(var(--border-hsl))" }}>
                <span style={{ display: "block", fontSize: "11px", color: "hsl(var(--text-hint-hsl))", marginBottom: "4px" }}>Закрыто обращений</span>
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
              Менеджеры
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
              Статистика
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
              <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff" }}>Настройки AI модели</h4>
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
                        {label} {isPending && "(обновление...)"}
                      </span>
                    </label>
                  );
                })}
              </div>
            ) : (
              <span style={{ fontSize: "12px", color: "hsl(var(--error-hsl))" }}>Не удалось загрузить настройки AI</span>
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
              <h4 style={{ margin: 0, fontSize: "14px", fontWeight: 700, color: "#fff" }}>История рассылок</h4>
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
              Создание рассылок доступно в Telegram-боте. Отправьте команду <b>/broadcast</b> боту, чтобы начать подготовку новой рассылки.
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
                      <span style={{ color: "hsl(var(--accent-hsl))" }}>Рассылка #{b.id}</span>
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
                      <span>Получатели: <b>{b.recipient_count}</b></span>
                      <span>Доставлено: <b style={{ color: "hsl(var(--success-hsl))" }}>{b.delivered_count}</b></span>
                      {b.failed_count > 0 && <span>Ошибка: <b style={{ color: "hsl(var(--error-hsl))" }}>{b.failed_count}</b></span>}
                      {b.blocked_count > 0 && <span>Блок: <b style={{ color: "hsl(var(--warning-hsl))" }}>{b.blocked_count}</b></span>}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <span style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>История рассылок пуста</span>
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
        Выйти из аккаунта
      </button>
    </div>
  );
};

export const App: React.FC = () => {
  const [profile, setProfile] = useState<UserProfile | null>(() => {
    const cached = localStorage.getItem("tma_user_profile");
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch (e) {
        localStorage.removeItem("tma_user_profile");
      }
    }
    return null;
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null);
  const [isMockActive, setIsMockActive] = useState(false);
  const [diagnostics, setDiagnostics] = useState<DiagnosticsData | null>(null);
  const [currentTab, setCurrentTab] = useState<string>("");

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

  const handleAuthentication = async (initData: string, fromMock = false) => {
    setDiagnostics(prev => prev ? { ...prev, authAttempted: true } : null);
    try {
      setLoading(true);
      setError(null);
      
      // 1. Submit initData to POST /api/auth/telegram to get short-lived session token
      const authData = await authenticateTelegram(initData);
      setStoredToken(authData.token);
      setProfile(authData.profile);
      localStorage.setItem("tma_user_profile", JSON.stringify(authData.profile));
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
        errMsg = "Telegram-сессия недействительна. Откройте приложение заново из бота.";
      }

      setError({
        status: apiErr.status,
        message: errMsg,
      });
      clearStoredToken();
      localStorage.removeItem("tma_user_profile");
      setProfile(null);
    } finally {
      setLoading(false);
    }
  };

  const refreshProfile = async () => {
    const token = getStoredToken();
    if (!token) return;
    try {
      const freshProfile = await getMe();
      setProfile((prev) => {
        if (JSON.stringify(prev) !== JSON.stringify(freshProfile)) {
          localStorage.setItem("tma_user_profile", JSON.stringify(freshProfile));
          return freshProfile;
        }
        return prev;
      });
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.status === 401 || apiErr.status === 403) {
        clearStoredToken();
        localStorage.removeItem("tma_user_profile");
        setProfile(null);
        setError({
          status: apiErr.status,
          message: "Telegram-сессия недействительна. Откройте приложение заново из бота.",
        });
      }
    }
  };

  const initializeApp = async (forceFreshAuth = false) => {
    setError(null);
    if (forceFreshAuth) {
      clearStoredToken();
      localStorage.removeItem("tma_user_profile");
      setProfile(null);
      setIsMockActive(false);
    }

    // Read cached profile to determine if we can bypass full-screen loading
    const storedToken = forceFreshAuth ? null : getStoredToken();
    const cachedProfileStr = localStorage.getItem("tma_user_profile");
    let cachedProfile: UserProfile | null = null;
    if (cachedProfileStr) {
      try {
        cachedProfile = JSON.parse(cachedProfileStr);
        setProfile(cachedProfile);
      } catch (e) {
        localStorage.removeItem("tma_user_profile");
      }
    }

    if (storedToken && cachedProfile) {
      setLoading(false);
    } else {
      setLoading(true);
    }

    // Wait for Telegram WebApp and initData with mobile-safe backoff.
    const { webApp, initData } = await waitForTelegramLaunchContext();

    const hasTg = typeof window !== "undefined" && !!window.Telegram;
    const hasWebApp = !!webApp;
    const initDataLen = initData.length;
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

    if (initData) {
      // Always authenticate using initData if available
      clearStoredToken();
      await handleAuthentication(initData, false);
    } else if (storedToken) {
      // Fetch fresh profile using existing token
      setDiagnostics(prev => prev ? { ...prev, authAttempted: true } : null);
      try {
        const freshProfile = await getMe();
        setProfile(freshProfile);
        localStorage.setItem("tma_user_profile", JSON.stringify(freshProfile));
        setIsMockActive(storedToken.includes(".mock_") || !webApp);
        setError(null);
      } catch (err) {
        clearStoredToken();
        localStorage.removeItem("tma_user_profile");
        setProfile(null);
        const apiErr = err as ApiError;
        currentDiagnostics.errorStatus = apiErr.status;
        currentDiagnostics.errorType = apiErr.message || "Session verification failed";
        setDiagnostics({ ...currentDiagnostics });

        if (isDev) {
          setError(null);
        } else {
          setError({
            status: apiErr.status || 401,
            message: "Telegram-сессия недействительна. Откройте приложение заново из бота.",
          });
        }
      } finally {
        setLoading(false);
      }
    } else {
      // No initData and no stored token
      localStorage.removeItem("tma_user_profile");
      setProfile(null);
      if (isDev) {
        setLoading(false);
      } else {
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
      localStorage.removeItem("tma_user_profile");
      setError({
        status: 401,
        message: "Telegram-сессия недействительна. Откройте приложение заново из бота.",
      });
    });

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        refreshProfile();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      unsubscribe();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    if (profile) {
      refreshProfile();
    }
  }, [currentTab]);

  const handleSelectMockRole = async (role: "customer" | "manager" | "owner" | "co_owner") => {
    const mockInitData = getMockInitData(role);
    // Local mock tokens will contain '.mock_' for detection
    await handleAuthentication(mockInitData, true);
  };

  const handleLogout = () => {
    clearStoredToken();
    localStorage.removeItem("tma_user_profile");
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
        onRetry={() => initializeApp(true)}
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
          <>
            {currentTab === "chats" && <CustomerHomePage onSelectTicket={setSelectedTicketId} />}
            {currentTab === "new_chat" && <NewChatView onSelectTicket={setSelectedTicketId} setActiveTab={setCurrentTab} />}
            {currentTab === "ai_helper" && <AIChatPage />}
            {currentTab === "profile" && (
              <ProfileView 
                profile={profile} 
                onLogout={handleLogout} 
                isMockActive={isMockActive} 
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
              />
            )}
            {currentTab === "ai_helper" && <AIChatPage />}
            {currentTab === "profile" && (
              <ProfileView 
                profile={profile} 
                onLogout={handleLogout} 
                isMockActive={isMockActive} 
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
              />
            )}
            {currentTab === "ai_helper" && <AIChatPage />}
            {currentTab === "more" && (
              <ProfileView 
                profile={profile} 
                onLogout={handleLogout} 
                isMockActive={isMockActive} 
                setCurrentTab={setCurrentTab}
                setProfile={setProfile}
              />
            )}
          </>
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
              Chats
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
              New Chat
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
              AI Helper
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
              Profile
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
              New Queue
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
              Active Chats
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
              Closed Chats
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
              AI Helper
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
              Profile
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
              Overview
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
              Managers
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
              Stats
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
              AI Helper
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
              More
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default App;
