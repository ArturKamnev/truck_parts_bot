import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowLeft,
  BarChart3,
  Bot,
  CheckCircle2,
  Clock3,
  Copy,
  FileText,
  Inbox,
  Layers,
  Plus,
  Radio,
  Search,
  ShieldAlert,
  Trash2,
  Users,
  X,
} from "lucide-react";
import {
  clearCancelledTicketsFromView,
  clearClosedTicketsFromView,
  closeStaleOpenTickets,
  getOwnerManagers,
  getOwnerOverview,
  getOwnerTickets,
  getOwnerUsers,
  promoteCoOwner,
  promoteManager,
  disableCoOwner,
  disableManager,
  getManagerStats,
  type BotUser,
  type ManagerStats,
  type OwnerOverview,
  type StaffMember,
  type Ticket,
} from "../api/tickets";
import { TicketCard } from "../components/TicketCard";
import { EmptyState } from "../components/EmptyState";
import { BarList, DonutChart, Sparkline, StatCard } from "../components/MiniCharts";
import { type ApiError } from "../api/client";
import { t } from "../i18n";

interface OwnerDashboardPageProps {
  onSelectTicket: (ticketId: number) => void;
  activeTab?: "dashboard" | "managers" | "stats";
  setActiveTab?: (tab: "dashboard" | "managers" | "stats") => void;
  locale: string;
}

type TicketStatusFilter = "all" | "OPEN" | "CLAIMED" | "CLOSED" | "CANCELLED_BY_CUSTOMER";

const secondsLabel = (seconds: number | null | undefined, locale: string) => {
  if (seconds === null || seconds === undefined) return t("stats.not_available", locale);
  return t("stats.seconds", locale).replace("{n}", String(Math.round(seconds)));
};

const ticketStatusLabel = (status: string, locale: string) => {
  const key = `ticket.status_${status.toLowerCase()}`;
  return t(key, locale);
};

export const OwnerDashboardPage: React.FC<OwnerDashboardPageProps> = ({
  onSelectTicket,
  activeTab: externalActiveTab,
  setActiveTab: externalSetActiveTab,
  locale,
}) => {
  const [internalActiveTab, setInternalActiveTab] = useState<"dashboard" | "managers" | "stats">("dashboard");
  const activeTab = externalActiveTab || internalActiveTab;
  const setActiveTab = (tab: "dashboard" | "managers" | "stats") => {
    if (externalSetActiveTab) externalSetActiveTab(tab);
    else setInternalActiveTab(tab);
  };

  const [overview, setOverview] = useState<OwnerOverview | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [managers, setManagers] = useState<StaffMember[]>([]);
  const [botUsers, setBotUsers] = useState<BotUser[]>([]);
  const [managersStats, setManagersStats] = useState<Record<number, ManagerStats>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [query, setQuery] = useState("");
  const [ticketStatus, setTicketStatus] = useState<TicketStatusFilter>("all");
  const [managerFilter, setManagerFilter] = useState("all");
  const [hiddenStatuses, setHiddenStatuses] = useState<Set<string>>(new Set());
  const [showPromoteForm, setShowPromoteForm] = useState<number | null>(null);
  const [promoteNotes, setPromoteNotes] = useState("");
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  const [confirmDisableId, setConfirmDisableId] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const storedProfile = localStorage.getItem("tma_user_profile");
  let currentUserId: number | null = null;
  let currentRole: string | null = null;
  if (storedProfile) {
    try {
      const parsedProfile = JSON.parse(storedProfile);
      currentUserId = parsedProfile.telegram_user_id;
      currentRole = parsedProfile.role;
    } catch {
      currentUserId = null;
    }
  }
  const isRootOwner = currentRole === "owner";

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [overviewData, ticketsData] = await Promise.all([getOwnerOverview(), getOwnerTickets()]);
      setOverview(overviewData);
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
      const [managersData, usersData] = await Promise.all([getOwnerManagers(), getOwnerUsers()]);
      setManagers(managersData);
      setBotUsers(usersData);
      const statsResults = await Promise.all(
        managersData.map(async (manager) => {
          try {
            return { id: manager.telegram_user_id, stats: await getManagerStats(manager.telegram_user_id) };
          } catch {
            return { id: manager.telegram_user_id, stats: null };
          }
        })
      );
      const statsMap: Record<number, ManagerStats> = {};
      statsResults.forEach((result) => {
        if (result.stats) statsMap[result.id] = result.stats;
      });
      setManagersStats(statsMap);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "managers") fetchManagersData();
    else fetchDashboardData();
  }, [activeTab]);

  const filteredTickets = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return tickets.filter((ticket) => {
      if (hiddenStatuses.has(ticket.status)) return false;
      if (ticketStatus !== "all" && ticket.status !== ticketStatus) return false;
      if (managerFilter !== "all" && String(ticket.assigned_manager_telegram_id || "") !== managerFilter) return false;
      if (!normalizedQuery) return true;
      const haystack = [
        ticket.id,
        ticket.customer_id,
        ticket.customer_username,
        ticket.customer_first_name,
        ticket.customer_last_name,
        ticket.assigned_manager_telegram_id,
      ].join(" ").toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [tickets, query, ticketStatus, managerFilter, hiddenStatuses]);

  const filteredUsers = botUsers.filter((user) => {
    if (currentUserId && user.telegram_user_id === currentUserId) return false;
    const isActiveStaff = managers.some(
      (manager) => manager.telegram_user_id === user.telegram_user_id && manager.status === "active"
    );
    if (isActiveStaff) return false;
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return true;
    return [user.telegram_user_id, user.username, user.first_name, user.last_name]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery);
  });

  const handlePromote = async (telegramUserId: number) => {
    try {
      setSubmittingId(telegramUserId);
      setError(null);
      await promoteManager(telegramUserId, promoteNotes || undefined);
      setPromoteNotes("");
      setShowPromoteForm(null);
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
      if (staff.role === "co_owner") await disableCoOwner(staff.telegram_user_id);
      else await disableManager(staff.telegram_user_id);
      setConfirmDisableId(null);
      await fetchManagersData();
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setSubmittingId(null);
    }
  };

  const handleLocalClear = async (status: "CLOSED" | "CANCELLED_BY_CUSTOMER") => {
    try {
      const result = status === "CLOSED" ? await clearClosedTicketsFromView() : await clearCancelledTicketsFromView();
      setHiddenStatuses((prev) => new Set([...prev, status]));
      setActionMessage(t("owner.clear_result", locale).replace("{n}", String(result.affected_count)));
    } catch (err) {
      setError(err as ApiError);
    }
  };

  const handleCloseStale = async () => {
    if (!window.confirm(t("owner.close_stale_confirm", locale))) return;
    try {
      const result = await closeStaleOpenTickets(14);
      setActionMessage(t("owner.close_stale_result", locale).replace("{n}", String(result.affected_count)));
      await fetchDashboardData();
    } catch (err) {
      setError(err as ApiError);
    }
  };

  const handleCopySummary = async () => {
    if (!overview) return;
    const summary = [
      `${t("owner.system_overview", locale)}:`,
      `${t("stats.customers", locale)}: ${overview.total_users}`,
      `${t("stats.open_tickets", locale)}: ${overview.open_tickets}`,
      `${t("stats.claimed", locale)}: ${overview.active_chats}`,
      `${t("stats.closed", locale)}: ${overview.closed_tickets}`,
      `${t("owner.ai_requests_label", locale)}: ${overview.ai_requests_count}`,
    ].join("\n");
    await navigator.clipboard.writeText(summary);
    setActionMessage(t("common.copied", locale));
  };

  if (activeTab === "managers") {
    return (
      <div className="animate-fade-in" style={{ height: "100%", overflowY: "auto", padding: "16px", paddingBottom: "96px", display: "flex", flexDirection: "column", gap: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button onClick={() => setActiveTab("dashboard")} style={{ display: "flex", alignItems: "center", gap: "6px", color: "hsl(var(--accent-hsl))", fontWeight: 700, fontSize: "13px" }}>
            <ArrowLeft size={16} /> {t("owner.back_overview", locale)}
          </button>
          <button onClick={fetchManagersData} style={{ color: "hsl(var(--accent-hsl))", fontSize: "12px", fontWeight: 700 }}>
            {t("common.refresh", locale)}
          </button>
        </div>

        <div>
          <h2 style={{ fontSize: "20px", fontWeight: 800, marginBottom: "4px" }}>{t("owner.manage_staff", locale)}</h2>
          <p style={{ fontSize: "13px", color: "hsl(var(--text-hint-hsl))" }}>{t("owner.manage_staff_desc", locale)}</p>
        </div>

        {error && <ErrorBanner error={error} locale={locale} />}

        <SearchBox value={query} onChange={setQuery} placeholder={t("owner.search_users", locale)} />

        <section style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <h3 style={{ fontSize: "12px", fontWeight: 800, color: "hsl(var(--text-hint-hsl))" }}>
            {t("owner.active_staff", locale)} ({managers.length})
          </h3>
          {loading && managers.length === 0 ? (
            <div className="skeleton" style={{ height: "112px", borderRadius: "var(--radius-md)" }} />
          ) : managers.length === 0 ? (
            <EmptyState title={t("owner.no_managers", locale)} description={t("owner.no_managers_desc", locale)} />
          ) : (
            managers.map((manager) => {
              const stats = managersStats[manager.telegram_user_id];
              const isSelf = currentUserId === manager.telegram_user_id;
              const isProtected = isSelf || (!isRootOwner && manager.role === "co_owner");
              return (
                <div key={manager.id} className="premium-card" style={{ padding: "14px", display: "flex", flexDirection: "column", gap: "10px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: "12px" }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
                        <b style={{ fontSize: "15px" }}>{manager.display_name}</b>
                        <span style={{ color: "hsl(var(--accent-hsl))", fontSize: "10px", fontWeight: 800, textTransform: "uppercase" }}>
                          {manager.role === "co_owner" ? t("owner.role_co_owner", locale) : t("owner.role_manager", locale)}
                        </span>
                        {manager.status === "disabled" && (
                          <span style={{ color: "hsl(var(--danger-hsl))", fontSize: "10px", fontWeight: 800 }}>{t("owner.status_disabled", locale)}</span>
                        )}
                      </div>
                      <div style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>
                        Telegram ID {manager.telegram_user_id} {manager.username ? `@${manager.username}` : ""}
                      </div>
                    </div>
                    {!isProtected && (
                      confirmDisableId === manager.telegram_user_id ? (
                        <div style={{ display: "flex", gap: "6px" }}>
                          <button disabled={submittingId === manager.telegram_user_id} onClick={() => handleDisableStaff(manager)} style={{ color: "#fff", background: "hsl(var(--danger-hsl))", borderRadius: "8px", padding: "7px 9px", fontSize: "11px", fontWeight: 800 }}>
                            {t("common.confirm", locale)}
                          </button>
                          <button onClick={() => setConfirmDisableId(null)} style={{ color: "hsl(var(--text-hint-hsl))", padding: "7px" }}>
                            <X size={15} />
                          </button>
                        </div>
                      ) : (
                        <button onClick={() => setConfirmDisableId(manager.telegram_user_id)} style={{ color: "hsl(var(--danger-hsl))", border: "1px solid rgba(239,68,68,0.28)", borderRadius: "8px", padding: "7px 9px", fontSize: "11px", fontWeight: 800 }}>
                          {manager.role === "co_owner" ? t("owner.remove", locale) : t("owner.demote", locale)}
                        </button>
                      )
                    )}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px", borderTop: "1px solid hsl(var(--border-hsl))", paddingTop: "10px" }}>
                    <MiniNumber label={t("owner.claimed", locale)} value={stats?.tickets_claimed ?? 0} />
                    <MiniNumber label={t("owner.closed", locale)} value={stats?.tickets_closed ?? 0} />
                    <MiniNumber label={t("owner.notes", locale)} value={manager.notes || t("stats.not_available", locale)} />
                  </div>
                </div>
              );
            })
          )}
        </section>

        <section style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <h3 style={{ fontSize: "12px", fontWeight: 800, color: "hsl(var(--text-hint-hsl))" }}>{t("owner.promote_new", locale)}</h3>
          {filteredUsers.length === 0 ? (
            <EmptyState title={t("owner.no_users_match", locale)} description={t("owner.no_users_match_desc", locale)} />
          ) : (
            filteredUsers.map((user) => {
              const displayName = [user.first_name, user.last_name].filter(Boolean).join(" ") || user.username || `Telegram ID ${user.telegram_user_id}`;
              return (
                <div key={user.id} className="premium-card" style={{ padding: "12px", display: "flex", flexDirection: "column", gap: "10px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "10px" }}>
                    <div>
                      <b style={{ fontSize: "14px" }}>{displayName}</b>
                      <div style={{ fontSize: "11px", color: "hsl(var(--text-hint-hsl))" }}>
                        Telegram ID {user.telegram_user_id} {user.username ? `@${user.username}` : ""}
                      </div>
                    </div>
                    {showPromoteForm !== user.telegram_user_id && (
                      <button onClick={() => setShowPromoteForm(user.telegram_user_id)} style={{ display: "flex", alignItems: "center", gap: "5px", background: "hsl(var(--accent-hsl))", color: "#fff", borderRadius: "8px", padding: "8px 10px", fontSize: "12px", fontWeight: 800 }}>
                        <Plus size={13} /> {t("owner.promote", locale)}
                      </button>
                    )}
                  </div>
                  {showPromoteForm === user.telegram_user_id && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px", borderTop: "1px solid hsl(var(--border-hsl))", paddingTop: "10px" }}>
                      <input value={promoteNotes} onChange={(event) => setPromoteNotes(event.target.value)} placeholder={t("owner.notes_placeholder", locale)} style={{ border: "1px solid hsl(var(--border-hsl))", borderRadius: "8px", padding: "9px", background: "rgba(255,255,255,0.04)" }} />
                      <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", flexWrap: "wrap" }}>
                        <button disabled={submittingId === user.telegram_user_id} onClick={() => handlePromote(user.telegram_user_id)} style={{ background: "hsl(var(--accent-hsl))", color: "#fff", borderRadius: "8px", padding: "8px 10px", fontSize: "12px", fontWeight: 800 }}>
                          {t("owner.role_manager", locale)}
                        </button>
                        {isRootOwner && (
                          <button disabled={submittingId === user.telegram_user_id} onClick={() => handlePromoteCoOwner(user.telegram_user_id)} style={{ background: "hsl(var(--warning-hsl))", color: "#fff", borderRadius: "8px", padding: "8px 10px", fontSize: "12px", fontWeight: 800 }}>
                            {t("owner.role_co_owner", locale)}
                          </button>
                        )}
                        <button onClick={() => setShowPromoteForm(null)} style={{ color: "hsl(var(--text-hint-hsl))", padding: "8px" }}>
                          {t("common.cancel", locale)}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </section>
      </div>
    );
  }

  if (activeTab === "stats") {
    return (
      <div className="animate-fade-in" style={{ height: "100%", overflowY: "auto", padding: "16px", paddingBottom: "96px", display: "flex", flexDirection: "column", gap: "16px" }}>
        <PageHeader title={t("stats.system_statistics", locale)} onRefresh={fetchDashboardData} locale={locale} />
        {error ? (
          <EmptyState title={t("owner.stats_failed", locale)} description={error.message} actionLabel={t("common.retry", locale)} onAction={fetchDashboardData} />
        ) : loading && !overview ? (
          <SkeletonGrid />
        ) : overview ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "10px" }}>
              <StatCard icon={Users} label={t("stats.customers", locale)} value={overview.total_users} hint={t("owner.active_users_hint", locale).replace("{n}", String(overview.active_users))} />
              <StatCard icon={Inbox} label={t("stats.open_tickets", locale)} value={overview.open_tickets} tone="warning" hint={t("owner.pending_replies", locale).replace("{n}", String(overview.pending_chats))} />
              <StatCard icon={CheckCircle2} label={t("stats.closed", locale)} value={overview.closed_tickets} tone="success" />
              <StatCard icon={Bot} label={t("owner.ai_requests_label", locale)} value={overview.ai_requests_count} hint={overview.active_model || t("stats.not_available", locale)} />
            </div>
            <div className="premium-card" style={{ padding: "14px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <SectionTitle icon={BarChart3} label={t("owner.ticket_trend", locale)} />
              <Sparkline points={overview.ticket_trend} label={t("owner.no_chart_data", locale)} />
            </div>
            <div className="premium-card" style={{ padding: "14px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <SectionTitle icon={Layers} label={t("owner.tickets_by_status", locale)} />
              <BarList points={overview.tickets_by_status.map((point) => ({ ...point, label: ticketStatusLabel(point.label, locale) }))} emptyLabel={t("owner.no_chart_data", locale)} />
            </div>
            <div className="premium-card" style={{ padding: "14px", display: "grid", gridTemplateColumns: "78px 1fr", alignItems: "center", gap: "12px" }}>
              <DonutChart value={overview.broadcast_summary.delivered} total={overview.broadcast_summary.recipients} label={t("owner.broadcast_delivery", locale)} />
              <div>
                <SectionTitle icon={Radio} label={t("owner.broadcast_delivery", locale)} />
                <p style={{ margin: "8px 0 0", color: "hsl(var(--text-hint-hsl))", fontSize: "12px" }}>
                  {t("broadcast.delivered", locale)}: {overview.broadcast_summary.delivered} / {overview.broadcast_summary.recipients}
                </p>
                <p style={{ margin: "4px 0 0", color: "hsl(var(--text-hint-hsl))", fontSize: "12px" }}>
                  {t("broadcast.failed", locale)}: {overview.broadcast_summary.failed}, {t("broadcast.blocked", locale)}: {overview.broadcast_summary.blocked}
                </p>
              </div>
            </div>
            <div className="premium-card" style={{ padding: "14px", display: "flex", flexDirection: "column", gap: "12px" }}>
              <SectionTitle icon={Activity} label={t("owner.language_distribution", locale)} />
              <BarList points={overview.language_distribution} emptyLabel={t("owner.no_chart_data", locale)} />
            </div>
          </>
        ) : null}
      </div>
    );
  }

  return (
    <div className="animate-fade-in" style={{ height: "100%", overflowY: "auto", padding: "16px", paddingBottom: "96px", display: "flex", flexDirection: "column", gap: "16px" }}>
      <PageHeader title={t("owner.system_overview", locale)} onRefresh={fetchDashboardData} locale={locale} />
      {error && <ErrorBanner error={error} locale={locale} />}
      {actionMessage && (
        <div style={{ border: "1px solid hsl(var(--success-hsl))", color: "hsl(var(--success-hsl))", background: "rgba(34,197,94,0.08)", borderRadius: "8px", padding: "10px 12px", fontSize: "12px" }}>
          {actionMessage}
        </div>
      )}

      {loading && !overview ? (
        <SkeletonGrid />
      ) : overview ? (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "10px" }}>
            <StatCard icon={Users} label={t("stats.customers", locale)} value={overview.total_users} hint={t("owner.active_users_hint", locale).replace("{n}", String(overview.active_users))} />
            <StatCard icon={MessageIcon} label={t("owner.active_chats", locale)} value={overview.active_chats} hint={t("owner.pending_replies", locale).replace("{n}", String(overview.pending_chats))} />
            <StatCard icon={Clock3} label={t("stats.avg_claim_time", locale)} value={secondsLabel(overview.avg_first_claim_seconds, locale)} tone="neutral" />
            <StatCard icon={Bot} label={t("owner.active_ai_model", locale)} value={overview.active_model || t("stats.not_available", locale)} hint={t("owner.ai_requests_hint", locale).replace("{n}", String(overview.ai_requests_count))} />
          </div>

          <section style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "10px" }}>
            <ActionButton icon={Users} label={t("nav.managers", locale)} onClick={() => setActiveTab("managers")} />
            <ActionButton icon={BarChart3} label={t("nav.stats", locale)} onClick={() => setActiveTab("stats")} />
            <ActionButton icon={Copy} label={t("owner.copy_summary", locale)} onClick={handleCopySummary} />
            <ActionButton icon={Trash2} label={t("owner.close_stale", locale)} onClick={handleCloseStale} danger />
          </section>

          <div className="premium-card" style={{ padding: "14px", display: "flex", flexDirection: "column", gap: "12px" }}>
            <SectionTitle icon={Activity} label={t("owner.manager_performance", locale)} />
            {overview.manager_performance.length === 0 ? (
              <span style={{ color: "hsl(var(--text-hint-hsl))", fontSize: "12px" }}>{t("owner.no_managers", locale)}</span>
            ) : (
              overview.manager_performance.slice(0, 4).map((manager) => (
                <div key={manager.telegram_user_id} style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: "10px", alignItems: "center", fontSize: "12px" }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{manager.display_name}</span>
                  <b style={{ color: "hsl(var(--accent-hsl))" }}>{manager.active_tickets}</b>
                  <span style={{ color: "hsl(var(--text-hint-hsl))" }}>{manager.closed_tickets}</span>
                </div>
              ))
            )}
          </div>
        </>
      ) : null}

      <section style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: "8px", alignItems: "center" }}>
          <h3 style={{ fontSize: "12px", fontWeight: 800, color: "hsl(var(--text-hint-hsl))" }}>
            {t("owner.all_ticket_logs", locale)} ({filteredTickets.length})
          </h3>
          <button onClick={() => setHiddenStatuses(new Set())} style={{ color: "hsl(var(--accent-hsl))", fontSize: "12px", fontWeight: 700 }}>
            {t("owner.clear_filters", locale)}
          </button>
        </div>

        <SearchBox value={query} onChange={setQuery} placeholder={t("owner.search_tickets", locale)} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
          <select value={ticketStatus} onChange={(event) => setTicketStatus(event.target.value as TicketStatusFilter)} style={selectStyle}>
            <option value="all">{t("owner.filter_all_statuses", locale)}</option>
            <option value="OPEN">{t("chat.status_open", locale)}</option>
            <option value="CLAIMED">{t("chat.status_claimed", locale)}</option>
            <option value="CLOSED">{t("chat.status_closed", locale)}</option>
            <option value="CANCELLED_BY_CUSTOMER">{t("ticket.status_cancelled_by_customer", locale)}</option>
          </select>
          <select value={managerFilter} onChange={(event) => setManagerFilter(event.target.value)} style={selectStyle}>
            <option value="all">{t("owner.filter_all_managers", locale)}</option>
            {overview?.manager_performance.map((manager) => (
              <option key={manager.telegram_user_id} value={String(manager.telegram_user_id)}>{manager.display_name}</option>
            ))}
          </select>
        </div>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <button onClick={() => handleLocalClear("CLOSED")} style={chipButtonStyle}>{t("owner.clear_closed", locale)}</button>
          <button onClick={() => handleLocalClear("CANCELLED_BY_CUSTOMER")} style={chipButtonStyle}>{t("owner.clear_cancelled", locale)}</button>
        </div>

        {loading && tickets.length === 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {[1, 2].map((item) => <div key={item} className="skeleton" style={{ height: "94px", borderRadius: "var(--radius-md)" }} />)}
          </div>
        ) : filteredTickets.length === 0 ? (
          <EmptyState title={t("owner.no_tickets", locale)} description={t("owner.no_tickets_desc", locale)} />
        ) : (
          filteredTickets.slice(0, 30).map((ticket) => (
            <TicketCard key={ticket.id} ticket={ticket} showCustomerDetails onSelect={onSelectTicket} locale={locale} />
          ))
        )}
      </section>
    </div>
  );
};

const MessageIcon = FileText;

const selectStyle: React.CSSProperties = {
  border: "1px solid hsl(var(--border-hsl))",
  borderRadius: "8px",
  padding: "9px 10px",
  background: "hsl(var(--card-bg-hsl))",
  color: "#fff",
  fontSize: "12px",
};

const chipButtonStyle: React.CSSProperties = {
  border: "1px solid hsl(var(--border-hsl))",
  borderRadius: "999px",
  padding: "7px 10px",
  color: "hsl(var(--text-hint-hsl))",
  fontSize: "12px",
  fontWeight: 700,
};

const PageHeader: React.FC<{ title: string; onRefresh: () => void; locale: string }> = ({ title, onRefresh, locale }) => (
  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px" }}>
    <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 800 }}>{title}</h2>
    <button onClick={onRefresh} style={{ color: "hsl(var(--accent-hsl))", fontSize: "12px", fontWeight: 800 }}>
      {t("common.refresh", locale)}
    </button>
  </div>
);

const SectionTitle: React.FC<{ icon: React.ElementType; label: string }> = ({ icon: Icon, label }) => (
  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "hsl(var(--text-hint-hsl))", fontSize: "12px", fontWeight: 800 }}>
    <Icon size={15} style={{ color: "hsl(var(--accent-hsl))" }} />
    {label}
  </div>
);

const SearchBox: React.FC<{ value: string; onChange: (value: string) => void; placeholder: string }> = ({ value, onChange, placeholder }) => (
  <div style={{ display: "flex", alignItems: "center", gap: "8px", border: "1px solid hsl(var(--border-hsl))", borderRadius: "8px", padding: "9px 10px", background: "hsl(var(--card-bg-hsl))" }}>
    <Search size={15} style={{ color: "hsl(var(--text-hint-hsl))" }} />
    <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} style={{ flex: 1, fontSize: "13px" }} />
  </div>
);

const ErrorBanner: React.FC<{ error: ApiError; locale: string }> = ({ error, locale }) => (
  <div style={{ backgroundColor: "rgba(239,68,68,0.1)", border: "1px solid hsl(var(--danger-hsl))", borderRadius: "8px", padding: "12px", color: "hsl(var(--danger-hsl))", display: "flex", alignItems: "center", gap: "8px", fontSize: "13px" }}>
    <ShieldAlert size={16} />
    <span>{error.message || t("common.error", locale)}</span>
  </div>
);

const SkeletonGrid: React.FC = () => (
  <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "10px" }}>
    {[1, 2, 3, 4].map((item) => <div key={item} className="skeleton" style={{ height: "104px", borderRadius: "var(--radius-md)" }} />)}
  </div>
);

const MiniNumber: React.FC<{ label: string; value: string | number }> = ({ label, value }) => (
  <div>
    <div style={{ fontSize: "10px", color: "hsl(var(--text-hint-hsl))", marginBottom: "3px" }}>{label}</div>
    <b style={{ fontSize: "12px" }}>{value}</b>
  </div>
);

const ActionButton: React.FC<{ icon: React.ElementType; label: string; onClick: () => void; danger?: boolean }> = ({ icon: Icon, label, onClick, danger }) => (
  <button onClick={onClick} className="premium-card" style={{ padding: "12px", display: "flex", alignItems: "center", gap: "8px", color: danger ? "hsl(var(--danger-hsl))" : "hsl(var(--accent-hsl))", fontWeight: 800, fontSize: "12px" }}>
    <Icon size={16} />
    <span style={{ color: "#fff" }}>{label}</span>
  </button>
);
