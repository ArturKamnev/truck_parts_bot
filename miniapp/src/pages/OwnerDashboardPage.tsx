import React, { useEffect, useState } from "react";
import { Users, FileText, Activity, Layers, MessageSquare, Radio, ArrowLeft, Plus, X, Search, ShieldAlert } from "lucide-react";
import {
  getOwnerStats,
  getOwnerTickets,
  getOwnerManagers,
  getOwnerUsers,
  promoteManager,
  disableManager,
  promoteCoOwner,
  disableCoOwner,
  getManagerStats,
  type OwnerStats,
  type Ticket,
  type StaffMember,
  type BotUser,
  type ManagerStats,
} from "../api/tickets";
import { TicketCard } from "../components/TicketCard";
import { EmptyState } from "../components/EmptyState";
import { type ApiError } from "../api/client";

import { t } from "../i18n";

interface OwnerDashboardPageProps {
  onSelectTicket: (ticketId: number) => void;
  activeTab?: "dashboard" | "managers" | "stats";
  setActiveTab?: (tab: "dashboard" | "managers" | "stats") => void;
  locale: string;
}

export const OwnerDashboardPage: React.FC<OwnerDashboardPageProps> = ({ 
  onSelectTicket,
  activeTab: externalActiveTab,
  setActiveTab: externalSetActiveTab,
  locale
}) => {
  const [stats, setStats] = useState<OwnerStats | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [managers, setManagers] = useState<StaffMember[]>([]);
  const [botUsers, setBotUsers] = useState<BotUser[]>([]);
  const [managersStats, setManagersStats] = useState<Record<number, ManagerStats>>({});
  
  const [internalActiveTab, setInternalActiveTab] = useState<"dashboard" | "managers" | "stats">("dashboard");
  
  const activeTab = externalActiveTab || internalActiveTab;
  const setActiveTab = (tab: "dashboard" | "managers" | "stats") => {
    if (externalSetActiveTab) {
      externalSetActiveTab(tab);
    } else {
      setInternalActiveTab(tab);
    }
  };
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  
  const [searchQuery, setSearchQuery] = useState("");
  const [showPromoteForm, setShowPromoteForm] = useState<number | null>(null);
  const [promoteNotes, setPromoteNotes] = useState("");
  
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  const [confirmDisableId, setConfirmDisableId] = useState<number | null>(null);

  // Get current logged in user ID from localStorage to protect demoting self/root
  const storedProfile = localStorage.getItem("tma_user_profile");
  let currentUserId: number | null = null;
  let currentRole: string | null = null;
  if (storedProfile) {
    try {
      const parsedProfile = JSON.parse(storedProfile);
      currentUserId = parsedProfile.telegram_user_id;
      currentRole = parsedProfile.role;
    } catch (e) {}
  }
  const isRootOwner = currentRole === "owner";

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [statsData, ticketsData] = await Promise.all([
        getOwnerStats(),
        getOwnerTickets(),
      ]);
      
      setStats(statsData);
      setTickets(ticketsData);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  const fetchManagersData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [managersData, usersData] = await Promise.all([
        getOwnerManagers(),
        getOwnerUsers(),
      ]);
      
      setManagers(managersData);
      setBotUsers(usersData);
      
      // Fetch stats for all managers in parallel
      const statsPromises = managersData.map(async (m) => {
        try {
          const mStats = await getManagerStats(m.telegram_user_id);
          return { id: m.telegram_user_id, stats: mStats };
        } catch (e) {
          return { id: m.telegram_user_id, stats: null };
        }
      });
      
      const statsResults = await Promise.all(statsPromises);
      const statsMap: Record<number, ManagerStats> = {};
      statsResults.forEach((res) => {
        if (res.stats) {
          statsMap[res.id] = res.stats;
        }
      });
      setManagersStats(statsMap);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "dashboard" || activeTab === "stats") {
      fetchDashboardData();
    } else {
      fetchManagersData();
    }
  }, [activeTab]);

  const handlePromote = async (telegramUserId: number) => {
    try {
      setSubmittingId(telegramUserId);
      setError(null);
      await promoteManager(telegramUserId, promoteNotes || undefined);
      setPromoteNotes("");
      setShowPromoteForm(null);
      // Refresh
      await fetchManagersData();
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setSubmittingId(null);
    }
  };

  const handleEnable = async (telegramUserId: number) => {
    try {
      setSubmittingId(telegramUserId);
      setError(null);
      // Enable is just promoting without modifying notes
      await promoteManager(telegramUserId);
      // Refresh
      await fetchManagersData();
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setSubmittingId(null);
    }
  };

  const handlePromoteCoOwner = async (telegramUserId: number) => {
    try {
      setSubmittingId(telegramUserId);
      setError(null);
      await promoteCoOwner(telegramUserId, promoteNotes || undefined);
      setPromoteNotes("");
      setShowPromoteForm(null);
      await fetchManagersData();
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setSubmittingId(null);
    }
  };

  const handleDisableStaff = async (staff: StaffMember) => {
    try {
      setSubmittingId(staff.telegram_user_id);
      setError(null);
      if (staff.role === "co_owner") {
        await disableCoOwner(staff.telegram_user_id);
      } else {
        await disableManager(staff.telegram_user_id);
      }
      setConfirmDisableId(null);
      await fetchManagersData();
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setSubmittingId(null);
    }
  };

  // Filter bot users for promotion list:
  // Exclude current owner, users who are already active managers, and filter by search
  const filteredUsers = botUsers.filter((u) => {
    // Exclude owner
    if (currentUserId && u.telegram_user_id === currentUserId) return false;
    
    // Exclude if already an active manager
    const isActiveManager = managers.some(
      (m) => m.telegram_user_id === u.telegram_user_id && m.status === "active"
    );
    if (isActiveManager) return false;

    if (!searchQuery) return true;
    const q = typeof searchQuery === "string" ? searchQuery.toLowerCase() : "";
    const username = typeof u.username === "string" ? u.username.toLowerCase() : "";
    const firstName = typeof u.first_name === "string" ? u.first_name.toLowerCase() : "";
    const lastName = typeof u.last_name === "string" ? u.last_name.toLowerCase() : "";
    const idStr = String(u.telegram_user_id || "");
    
    return (
      username.includes(q) ||
      firstName.includes(q) ||
      lastName.includes(q) ||
      idStr.includes(q)
    );
  });

  if (activeTab === "managers") {
    return (
      <div
        className="animate-fade-in"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          padding: "16px",
          overflowY: "auto",
          height: "100%",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button
            onClick={() => setActiveTab("dashboard")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: "none",
              border: "none",
              color: "hsl(var(--accent-hsl))",
              fontWeight: 600,
              fontSize: "14px",
              cursor: "pointer",
              padding: 0,
            }}
          >
            <ArrowLeft size={16} /> {t("owner.back_overview", locale)}
          </button>
          <button
            onClick={fetchManagersData}
            style={{
              background: "none",
              border: "none",
              fontSize: "12px",
              color: "hsl(var(--accent-hsl))",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {t("common.refresh", locale)}
          </button>
        </div>

        <div>
          <h2 style={{ fontSize: "20px", fontWeight: 800, marginBottom: "4px" }}>
            {t("owner.manage_staff", locale)}
          </h2>
          <p style={{ fontSize: "13px", color: "hsl(var(--text-hint-hsl))" }}>
            {t("owner.manage_staff_desc", locale)}
          </p>
        </div>

        {error && (
          <div
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgb(239, 68, 68)",
              borderRadius: "var(--radius-md)",
              padding: "12px",
              fontSize: "13px",
              color: "rgb(239, 68, 68)",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <ShieldAlert size={16} />
            <span>{error.message || t("common.error", locale)}</span>
          </div>
        )}

        {/* Section 1: Active Managers */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, color: "hsl(var(--text-hint-hsl))", letterSpacing: "0.05em" }}>
            {t("owner.active_staff", locale)} ({managers.length})
          </h3>

          {loading && managers.length === 0 ? (
            <div className="skeleton" style={{ height: "120px", borderRadius: "var(--radius-md)" }} />
          ) : managers.length === 0 ? (
            <EmptyState
              title={t("owner.no_managers", locale)}
              description={t("owner.no_managers_desc", locale)}
            />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {managers.map((m) => {
                const mStats = managersStats[m.telegram_user_id];
                const isSelf = currentUserId && m.telegram_user_id === currentUserId;
                const isProtected = Boolean(isSelf) || (!isRootOwner && m.role === "co_owner");

                return (
                  <div
                    key={m.id}
                    style={{
                      backgroundColor: "hsl(var(--card-bg-hsl))",
                      border: "1px solid hsl(var(--border-hsl))",
                      borderRadius: "var(--radius-md)",
                      padding: "14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span style={{ fontWeight: 700, fontSize: "15px" }}>
                            {m.display_name}
                          </span>
                          {m.role === "owner" && (
                            <span
                              style={{
                                fontSize: "10px",
                                backgroundColor: "rgba(59, 130, 246, 0.15)",
                                color: "rgb(59, 130, 246)",
                                padding: "2px 6px",
                                borderRadius: "10px",
                                fontWeight: 700,
                              }}
                            >
                              {t("owner.role_owner", locale)}
                            </span>
                          )}
                          {m.role === "co_owner" && (
                            <span
                              style={{
                                fontSize: "10px",
                                backgroundColor: "rgba(245, 158, 11, 0.15)",
                                color: "rgb(245, 158, 11)",
                                padding: "2px 6px",
                                borderRadius: "10px",
                                fontWeight: 700,
                              }}
                            >
                              {t("owner.role_co_owner", locale)}
                            </span>
                          )}
                          {m.status === "disabled" && (
                            <span
                              style={{
                                fontSize: "10px",
                                backgroundColor: "rgba(239, 68, 68, 0.15)",
                                color: "rgb(239, 68, 68)",
                                padding: "2px 6px",
                                borderRadius: "10px",
                                fontWeight: 700,
                              }}
                            >
                              {t("owner.status_disabled", locale)}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))", marginTop: "2px" }}>
                          ID: {m.telegram_user_id} {m.username && `@${m.username}`}
                        </div>
                      </div>

                      {/* Deactivate/Activate Actions */}
                      {!isProtected && (
                        <div>
                          {m.status === "active" ? (
                            confirmDisableId === m.telegram_user_id ? (
                              <div style={{ display: "flex", gap: "6px" }}>
                                <button
                                  disabled={submittingId === m.telegram_user_id}
                                  onClick={() => handleDisableStaff(m)}
                                  style={{
                                    fontSize: "11px",
                                    fontWeight: 700,
                                    backgroundColor: "rgb(239, 68, 68)",
                                    color: "white",
                                    border: "none",
                                    borderRadius: "var(--radius-sm)",
                                    padding: "4px 8px",
                                    cursor: "pointer",
                                  }}
                                >
                                  {submittingId === m.telegram_user_id ? "..." : t("common.confirm", locale)}
                                </button>
                                <button
                                  onClick={() => setConfirmDisableId(null)}
                                  style={{
                                    fontSize: "11px",
                                    fontWeight: 600,
                                    backgroundColor: "rgba(255, 255, 255, 0.1)",
                                    color: "hsl(var(--text-main-hsl))",
                                    border: "1px solid hsl(var(--border-hsl))",
                                    borderRadius: "var(--radius-sm)",
                                    padding: "4px 8px",
                                    cursor: "pointer",
                                  }}
                                >
                                  {t("common.cancel", locale)}
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setConfirmDisableId(m.telegram_user_id)}
                                style={{
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  backgroundColor: "rgba(239, 68, 68, 0.1)",
                                  color: "rgb(239, 68, 68)",
                                  border: "1px solid rgba(239, 68, 68, 0.3)",
                                  borderRadius: "var(--radius-sm)",
                                  padding: "4px 8px",
                                  cursor: "pointer",
                                }}
                              >
                                {m.role === "manager" ? t("owner.demote", locale) : t("owner.remove", locale)}
                              </button>
                            )
                          ) : (
                            <button
                              disabled={submittingId === m.telegram_user_id}
                              onClick={() => handleEnable(m.telegram_user_id)}
                              style={{
                                fontSize: "11px",
                                fontWeight: 600,
                                  backgroundColor: "rgba(34, 197, 94, 0.1)",
                                  color: "rgb(34, 197, 94)",
                                  border: "1px solid rgba(34, 197, 94, 0.3)",
                                  borderRadius: "var(--radius-sm)",
                                padding: "4px 8px",
                                cursor: "pointer",
                              }}
                            >
                              {submittingId === m.telegram_user_id ? "..." : t("owner.activate", locale)}
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Stats & Notes Row */}
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        borderTop: "1px solid hsl(var(--border-hsl))",
                        paddingTop: "10px",
                        fontSize: "12px",
                      }}
                    >
                      <div style={{ display: "flex", gap: "12px", color: "hsl(var(--text-hint-hsl))" }}>
                        <span>
                          {t("owner.claimed", locale)}: <b>{mStats ? mStats.tickets_claimed : 0}</b>
                        </span>
                        <span>
                          {t("owner.closed", locale)}: <b>{mStats ? mStats.tickets_closed : 0}</b>
                        </span>
                      </div>
                      {m.notes && (
                        <div style={{ fontStyle: "italic", color: "hsl(var(--text-hint-hsl))" }}>
                          {t("owner.notes", locale)}: {m.notes}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Section 2: Promotable Users */}
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "10px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, color: "hsl(var(--text-hint-hsl))", letterSpacing: "0.05em" }}>
            {t("owner.promote_new", locale)}
          </h3>

          <div
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              backgroundColor: "hsl(var(--card-bg-hsl))",
              border: "1px solid hsl(var(--border-hsl))",
              borderRadius: "var(--radius-md)",
              padding: "8px 12px",
            }}
          >
            <Search size={16} style={{ color: "hsl(var(--text-hint-hsl))", marginRight: "8px" }} />
            <input
              type="text"
              placeholder={t("owner.search_users", locale)}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: "none",
                border: "none",
                color: "hsl(var(--text-main-hsl))",
                fontSize: "14px",
                width: "100%",
                outline: "none",
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
              >
                <X size={16} style={{ color: "hsl(var(--text-hint-hsl))" }} />
              </button>
            )}
          </div>

          {loading && botUsers.length === 0 ? (
            <div className="skeleton" style={{ height: "80px", borderRadius: "var(--radius-md)" }} />
          ) : filteredUsers.length === 0 ? (
            <div
              style={{
                textAlign: "center",
                padding: "20px",
                color: "hsl(var(--text-hint-hsl))",
                fontSize: "13px",
              }}
            >
              {t("owner.no_users_match", locale)}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {filteredUsers.map((u) => {
                const displayName = [u.first_name, u.last_name].filter(Boolean).join(" ") || `User {u.telegram_user_id}`;
                return (
                  <div
                    key={u.id}
                    style={{
                      backgroundColor: "hsl(var(--card-bg-hsl))",
                      border: "1px solid hsl(var(--border-hsl))",
                      borderRadius: "var(--radius-md)",
                      padding: "10px 12px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: "14px" }}>{displayName}</div>
                        <div style={{ fontSize: "11px", color: "hsl(var(--text-hint-hsl))" }}>
                          ID: {u.telegram_user_id} {u.username && `@${u.username}`}
                        </div>
                      </div>

                      {showPromoteForm !== u.telegram_user_id && (
                        <button
                          onClick={() => {
                            setShowPromoteForm(u.telegram_user_id);
                            setPromoteNotes("");
                          }}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                            fontSize: "11px",
                            fontWeight: 700,
                            backgroundColor: "hsl(var(--accent-hsl))",
                            color: "white",
                            border: "none",
                            borderRadius: "var(--radius-sm)",
                            padding: "4px 8px",
                            cursor: "pointer",
                          }}
                        >
                          <Plus size={12} /> {t("owner.promote", locale)}
                        </button>
                      )}
                    </div>

                    {showPromoteForm === u.telegram_user_id && (
                      <div
                        style={{
                          borderTop: "1px dashed hsl(var(--border-hsl))",
                          paddingTop: "8px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px",
                        }}
                      >
                        <input
                          type="text"
                          placeholder={t("owner.notes_placeholder", locale)}
                          value={promoteNotes}
                          onChange={(e) => setPromoteNotes(e.target.value)}
                          style={{
                            backgroundColor: "rgba(255, 255, 255, 0.05)",
                            border: "1px solid hsl(var(--border-hsl))",
                            borderRadius: "var(--radius-sm)",
                            padding: "6px 8px",
                            fontSize: "12px",
                            color: "hsl(var(--text-main-hsl))",
                            outline: "none",
                          }}
                        />
                        <div style={{ display: "flex", gap: "6px", alignSelf: "flex-end", flexWrap: "wrap" }}>
                          <button
                            disabled={submittingId === u.telegram_user_id}
                            onClick={() => handlePromote(u.telegram_user_id)}
                            style={{
                              fontSize: "11px",
                              fontWeight: 700,
                              backgroundColor: "hsl(var(--accent-hsl))",
                              color: "white",
                              border: "none",
                              borderRadius: "var(--radius-sm)",
                              padding: "4px 8px",
                              cursor: "pointer",
                            }}
                          >
                            {submittingId === u.telegram_user_id ? t("common.saving", locale) : t("owner.role_manager", locale)}
                          </button>
                          {isRootOwner && (
                            <button
                              disabled={submittingId === u.telegram_user_id}
                              onClick={() => handlePromoteCoOwner(u.telegram_user_id)}
                              style={{
                                fontSize: "11px",
                                fontWeight: 700,
                                backgroundColor: "rgb(245, 158, 11)",
                                color: "white",
                                border: "none",
                                borderRadius: "var(--radius-sm)",
                                padding: "4px 8px",
                                cursor: "pointer",
                              }}
                            >
                              {t("owner.role_co_owner", locale)}
                            </button>
                          )}
                          <button
                            onClick={() => setShowPromoteForm(null)}
                            style={{
                              fontSize: "11px",
                              fontWeight: 600,
                              backgroundColor: "transparent",
                              color: "hsl(var(--text-hint-hsl))",
                              border: "none",
                              cursor: "pointer",
                            }}
                          >
                            {t("common.cancel", locale)}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (activeTab === "stats") {
    let errorTitle = t("common.error", locale);
    let errorDesc = error?.message || "";
    
    if (error) {
      if (error.status === 401 || error.status === 403) {
        errorTitle = t("error.restricted_access", locale);
        errorDesc = t("error.restricted_access_desc", locale);
      } else if (error.status === 500 || error.status === 0) {
        errorTitle = t("error.connection_failure_title", locale);
        errorDesc = t("error.connection_failure", locale);
      }
    }

    const totalCustomers = stats?.total_customers ?? 0;
    const openTickets = stats?.open_tickets ?? 0;
    const claimedTickets = stats?.claimed_tickets ?? 0;
    const closedTickets = stats?.closed_tickets ?? 0;
    const avgClaimTime = stats?.avg_first_claim_seconds !== undefined && stats?.avg_first_claim_seconds !== null
      ? t("stats.seconds", locale).replace("{n}", String(Math.round(stats.avg_first_claim_seconds)))
      : "N/A";
    const totalTickets = stats?.total_tickets ?? 0;
    const totalAiMessages = stats?.total_ai_messages ?? 0;
    const newCustomersToday = stats?.new_customers_today ?? 0;

    return (
      <div
        className="animate-fade-in"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          padding: "16px",
          overflowY: "auto",
          height: "100%",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: "16px", fontWeight: 700, letterSpacing: "0.05em", color: "hsl(var(--text-hint-hsl))", margin: 0 }}>
            {t("stats.system_statistics", locale)}
          </h2>
          <button
            onClick={fetchDashboardData}
            style={{ fontSize: "12px", color: "hsl(var(--accent-hsl))", fontWeight: 600, background: "none", border: "none", cursor: "pointer" }}
          >
            {t("common.refresh", locale)}
          </button>
        </div>

        {/* Grid of stats */}
        {loading && stats === null ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton" style={{ height: "80px", borderRadius: "var(--radius-md)" }} />
            ))}
          </div>
        ) : error ? (
          <EmptyState title={errorTitle} description={errorDesc} actionLabel={t("common.retry", locale)} onAction={fetchDashboardData} />
        ) : stats ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
              <div style={{ backgroundColor: "hsl(var(--card-bg-hsl))", border: "1px solid hsl(var(--border-hsl))", borderRadius: "var(--radius-md)", padding: "12px 14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "hsl(var(--accent-hsl))", marginBottom: "4px" }}>
                  <Users size={14} />
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("stats.customers", locale)}</span>
                </div>
                <span style={{ fontSize: "20px", fontWeight: 700 }}>{totalCustomers}</span>
              </div>
              <div style={{ backgroundColor: "hsl(var(--card-bg-hsl))", border: "1px solid hsl(var(--border-hsl))", borderRadius: "var(--radius-md)", padding: "12px 14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "hsl(var(--warning-hsl))", marginBottom: "4px" }}>
                  <Layers size={14} />
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("stats.open_tickets", locale)}</span>
                </div>
                <span style={{ fontSize: "20px", fontWeight: 700 }}>{openTickets}</span>
              </div>
              <div style={{ backgroundColor: "hsl(var(--card-bg-hsl))", border: "1px solid hsl(var(--border-hsl))", borderRadius: "var(--radius-md)", padding: "12px 14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "hsl(var(--accent-hsl))", marginBottom: "4px" }}>
                  <MessageSquare size={14} />
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("stats.claimed", locale)}</span>
                </div>
                <span style={{ fontSize: "20px", fontWeight: 700 }}>{claimedTickets}</span>
              </div>
              <div style={{ backgroundColor: "hsl(var(--card-bg-hsl))", border: "1px solid hsl(var(--border-hsl))", borderRadius: "var(--radius-md)", padding: "12px 14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "hsl(var(--text-hint-hsl))", marginBottom: "4px" }}>
                  <FileText size={14} />
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("stats.closed", locale)}</span>
                </div>
                <span style={{ fontSize: "20px", fontWeight: 700 }}>{closedTickets}</span>
              </div>
            </div>
            
            <div style={{ backgroundColor: "hsl(var(--card-bg-hsl))", border: "1px solid hsl(var(--border-hsl))", borderRadius: "var(--radius-md)", padding: "16px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <span style={{ fontSize: "12px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("stats.performance_metrics", locale)}</span>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "14px" }}>
                <span>{t("stats.avg_claim_time", locale)}</span>
                <span style={{ fontWeight: 700, color: "hsl(var(--accent-hsl))" }}>
                  {avgClaimTime}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "14px" }}>
                <span>{t("stats.total_tickets", locale)}</span>
                <span style={{ fontWeight: 700 }}>{totalTickets}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "14px" }}>
                <span>{t("stats.total_ai_messages", locale)}</span>
                <span style={{ fontWeight: 700 }}>{totalAiMessages}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "14px" }}>
                <span>{t("stats.new_customers_today", locale)}</span>
                <span style={{ fontWeight: 700, color: "hsl(var(--success-hsl))" }}>{newCustomersToday}</span>
              </div>
            </div>
          </div>
        ) : (
          <EmptyState title="No statistics data" description="Click refresh to load statistics data." actionLabel={t("common.refresh", locale)} onAction={fetchDashboardData} />
        )}
      </div>
    );
  }

  return (
    <div
      className="animate-fade-in"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "20px",
        padding: "16px",
        overflowY: "auto",
        height: "100%",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ fontSize: "16px", fontWeight: 700, letterSpacing: "0.05em", color: "hsl(var(--text-hint-hsl))" }}>
          {t("owner.system_overview", locale)}
        </h2>
        <button
          onClick={fetchDashboardData}
          style={{ fontSize: "12px", color: "hsl(var(--accent-hsl))", fontWeight: 600, background: "none", border: "none", cursor: "pointer" }}
        >
          {t("common.refresh", locale)}
        </button>
      </div>

      {/* Grid of stats */}
      {loading && stats === null ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="skeleton"
              style={{ height: "80px", borderRadius: "var(--radius-md)" }}
            />
          ))}
        </div>
      ) : error ? (
        <EmptyState
          title={t("owner.stats_failed", locale)}
          description={error.message}
          actionLabel={t("common.retry", locale)}
          onAction={fetchDashboardData}
        />
      ) : stats ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
          <div
            style={{
              backgroundColor: "hsl(var(--card-bg-hsl))",
              border: "1px solid hsl(var(--border-hsl))",
              borderRadius: "var(--radius-md)",
              padding: "12px 14px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "hsl(var(--accent-hsl))", marginBottom: "4px" }}>
              <Users size={14} />
              <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("stats.customers", locale)}</span>
            </div>
            <span style={{ fontSize: "20px", fontWeight: 700 }}>{stats.total_customers}</span>
          </div>

          <div
            style={{
              backgroundColor: "hsl(var(--card-bg-hsl))",
              border: "1px solid hsl(var(--border-hsl))",
              borderRadius: "var(--radius-md)",
              padding: "12px 14px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "hsl(var(--warning-hsl))", marginBottom: "4px" }}>
              <Layers size={14} />
              <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("stats.open_tickets", locale)}</span>
            </div>
            <span style={{ fontSize: "20px", fontWeight: 700 }}>{stats.open_tickets}</span>
          </div>

          <div
            style={{
              backgroundColor: "hsl(var(--card-bg-hsl))",
              border: "1px solid hsl(var(--border-hsl))",
              borderRadius: "var(--radius-md)",
              padding: "12px 14px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "hsl(var(--accent-hsl))", marginBottom: "4px" }}>
              <MessageSquare size={14} />
              <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("stats.claimed", locale)}</span>
            </div>
            <span style={{ fontSize: "20px", fontWeight: 700 }}>{stats.claimed_tickets}</span>
          </div>

          <div
            style={{
              backgroundColor: "hsl(var(--card-bg-hsl))",
              border: "1px solid hsl(var(--border-hsl))",
              borderRadius: "var(--radius-md)",
              padding: "12px 14px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "hsl(var(--text-hint-hsl))", marginBottom: "4px" }}>
              <FileText size={14} />
              <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("stats.closed", locale)}</span>
            </div>
            <span style={{ fontSize: "20px", fontWeight: 700 }}>{stats.closed_tickets}</span>
          </div>
        </div>
      ) : null}

      {/* Placeholders / Control card section */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
        {/* Manager Overview Card */}
        <div
          onClick={() => setActiveTab("managers")}
          style={{
            backgroundColor: "hsl(var(--card-bg-hsl))",
            border: "1px solid hsl(var(--border-hsl))",
            borderRadius: "var(--radius-md)",
            padding: "14px",
            cursor: "pointer",
            transition: "all 0.2s ease-in-out",
          }}
          className="interactive-card"
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
            <Activity size={14} style={{ color: "hsl(var(--accent-hsl))" }} />
            <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("owner.managers_state", locale)}</span>
          </div>
          <span style={{ fontSize: "12px", fontWeight: 600, color: "hsl(var(--accent-hsl))" }}>{t("owner.manage_staff", locale)} →</span>
        </div>

        {/* Broadcasts Card */}
        <div
          style={{
            backgroundColor: "hsl(var(--card-bg-hsl))",
            border: "1px solid hsl(var(--border-hsl))",
            borderRadius: "var(--radius-md)",
            padding: "14px",
            opacity: 0.6,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
            <Radio size={14} style={{ color: "hsl(var(--accent-hsl))" }} />
            <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>{t("nav.broadcasts", locale)}</span>
          </div>
          <span style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>{t("owner.broadcast_control", locale)}</span>
        </div>
      </div>

      {/* Ticket Logs List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: 700, color: "hsl(var(--text-hint-hsl))", letterSpacing: "0.05em" }}>
          {t("owner.all_ticket_logs", locale)} ({tickets.length})
        </h3>

        {loading && tickets.length === 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {[1, 2].map((i) => (
              <div
                key={i}
                className="skeleton"
                style={{ height: "94px", width: "100%", borderRadius: "var(--radius-md)" }}
              />
            ))}
          </div>
        ) : tickets.length === 0 ? (
          <EmptyState
            title={t("owner.no_tickets", locale)}
            description={t("owner.no_tickets_desc", locale)}
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {tickets.map((ticket) => (
              <TicketCard
                key={ticket.id}
                ticket={ticket}
                showCustomerDetails={true}
                onSelect={onSelectTicket}
                locale={locale}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
