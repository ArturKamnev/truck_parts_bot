import React, { useEffect, useState } from "react";
import { Inbox, MessageSquare, CheckCircle2, Clock3, RefreshCw, Search, X } from "lucide-react";
import { getManagerNewTickets, getManagerActiveTickets, getManagerClosedTickets, getManagerOverview, claimTicket, type ManagerOverview, type Ticket } from "../api/tickets";
import { TicketCard } from "../components/TicketCard";
import { EmptyState } from "../components/EmptyState";
import { Sparkline, StatCard } from "../components/MiniCharts";
import { type ApiError } from "../api/client";
import { t } from "../i18n";

interface ManagerDashboardPageProps {
  onSelectTicket: (ticketId: number) => void;
  activeTab?: TabType;
  setActiveTab?: (tab: TabType) => void;
  locale: string;
}

type TabType = "new" | "active" | "closed";

export const ManagerDashboardPage: React.FC<ManagerDashboardPageProps> = ({ 
  onSelectTicket,
  activeTab: externalActiveTab,
  setActiveTab: externalSetActiveTab,
  locale
}) => {
  const [internalActiveTab, setInternalActiveTab] = useState<TabType>("active");
  const activeTab = externalActiveTab || internalActiveTab;
  const setActiveTab = (tab: TabType) => {
    if (externalSetActiveTab) {
      externalSetActiveTab(tab);
    } else {
      setInternalActiveTab(tab);
    }
  };
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [overview, setOverview] = useState<ManagerOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [query, setQuery] = useState("");

  const fetchTickets = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [overviewData, data] = await Promise.all([
        getManagerOverview(),
        activeTab === "new"
        ? await getManagerNewTickets() 
        : activeTab === "active"
          ? await getManagerActiveTickets()
          : await getManagerClosedTickets()
      ]);
        
      setOverview(overviewData);
      setTickets(data);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  const handleClaim = async (ticketId: number) => {
    try {
      await claimTicket(ticketId);
      // Refresh list to update status
      fetchTickets();
    } catch (err) {
      const apiErr = err as ApiError;
      alert(apiErr.message || t("manager.claim_failed", locale));
      fetchTickets();
    }
  };

  useEffect(() => {
    fetchTickets();
  }, [activeTab]);

  const filteredTickets = tickets.filter((ticket) => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return true;
    return [
      ticket.id,
      ticket.customer_id,
      ticket.customer_username,
      ticket.customer_first_name,
      ticket.customer_last_name,
    ].join(" ").toLowerCase().includes(normalizedQuery);
  });

  const avgClose = overview?.avg_close_seconds === null || overview?.avg_close_seconds === undefined
    ? t("stats.not_available", locale)
    : t("stats.seconds", locale).replace("{n}", String(Math.round(overview.avg_close_seconds)));

  return (
    <div
      className="animate-fade-in"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
      }}
    >
      {/* Subheader tabs */}
      <div
        style={{
          display: "flex",
          backgroundColor: "hsl(var(--card-bg-hsl))",
          borderBottom: "1px solid hsl(var(--border-hsl))",
          padding: "4px 8px",
          gap: "8px",
        }}
      >
        <button
          onClick={() => setActiveTab("active")}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            padding: "8px 0",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            fontWeight: 600,
            color: activeTab === "active" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
            backgroundColor: activeTab === "active" ? "rgba(82, 136, 193, 0.08)" : "transparent",
            background: "none",
            border: "none",
            cursor: "pointer"
          }}
        >
          <MessageSquare size={16} />
          {t("manager.my_active_chats", locale)}
        </button>
        <button
          onClick={() => setActiveTab("new")}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            padding: "8px 0",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            fontWeight: 600,
            color: activeTab === "new" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
            backgroundColor: activeTab === "new" ? "rgba(82, 136, 193, 0.08)" : "transparent",
            background: "none",
            border: "none",
            cursor: "pointer"
          }}
        >
          <Inbox size={16} />
          {t("manager.new_tickets_queue", locale)}
        </button>
        <button
          onClick={() => setActiveTab("closed")}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            padding: "8px 0",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            fontWeight: 600,
            color: activeTab === "closed" ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
            backgroundColor: activeTab === "closed" ? "rgba(82, 136, 193, 0.08)" : "transparent",
            background: "none",
            border: "none",
            cursor: "pointer"
          }}
        >
          <CheckCircle2 size={16} />
          {t("manager.closed_chats", locale)}
        </button>
      </div>

      {/* Main ticket list view */}
      <div
        style={{
          flex: 1,
          padding: "16px",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        {overview && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "10px" }}>
            <StatCard icon={MessageSquare} label={t("manager.overview_active", locale)} value={overview.my_active_chats} />
            <StatCard icon={Inbox} label={t("manager.overview_queue", locale)} value={overview.available_queue} tone="warning" />
            <StatCard icon={CheckCircle2} label={t("manager.overview_closed", locale)} value={overview.my_closed_chats} tone="success" />
            <StatCard icon={Clock3} label={t("manager.overview_avg_close", locale)} value={avgClose} tone="neutral" />
          </div>
        )}

        {overview && (
          <div className="premium-card" style={{ padding: "12px", display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "12px", fontWeight: 800, color: "hsl(var(--text-hint-hsl))" }}>
                {t("manager.personal_trend", locale)}
              </span>
              <span style={{ fontSize: "11px", color: "hsl(var(--warning-hsl))" }}>
                {t("manager.pending_replies", locale).replace("{n}", String(overview.pending_replies))}
              </span>
            </div>
            <Sparkline points={overview.ticket_trend} label={t("owner.no_chart_data", locale)} />
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: "12px", fontWeight: 700, letterSpacing: "0.05em", color: "hsl(var(--text-hint-hsl))" }}>
            {activeTab === "new" ? t("manager.unclaimed_queue", locale) : activeTab === "active" ? t("manager.assigned_tickets", locale) : t("manager.closed_chats_list", locale)} ({filteredTickets.length})
          </span>
          <button onClick={fetchTickets} title={t("common.refresh", locale)} style={{ color: "hsl(var(--accent-hsl))", display: "flex", alignItems: "center" }}>
            <RefreshCw size={16} />
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", border: "1px solid hsl(var(--border-hsl))", borderRadius: "8px", padding: "9px 10px", background: "hsl(var(--card-bg-hsl))" }}>
          <Search size={15} style={{ color: "hsl(var(--text-hint-hsl))" }} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("manager.search_chats", locale)} style={{ flex: 1, fontSize: "13px" }} />
          {query && (
            <button onClick={() => setQuery("")} title={t("owner.clear_filters", locale)} style={{ color: "hsl(var(--text-hint-hsl))" }}>
              <X size={15} />
            </button>
          )}
        </div>

        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="skeleton"
                style={{ height: "94px", width: "100%", borderRadius: "var(--radius-md)" }}
              />
            ))}
          </div>
        ) : error ? (
          <EmptyState
            title={t("manager.load_failed", locale)}
            description={error.message}
            actionLabel={t("common.retry", locale)}
            onAction={fetchTickets}
          />
        ) : filteredTickets.length === 0 ? (
          <EmptyState
            title={activeTab === "new" ? t("manager.queue_empty", locale) : activeTab === "active" ? t("manager.no_active", locale) : t("manager.no_closed", locale)}
            description={
              activeTab === "new"
                ? t("manager.queue_empty_desc", locale)
                : activeTab === "active"
                  ? t("manager.no_active_desc", locale)
                  : t("manager.no_closed_desc", locale)
            }
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {filteredTickets.map((ticket) => (
              <TicketCard
                key={ticket.id}
                ticket={ticket}
                showCustomerDetails={true}
                onSelect={onSelectTicket}
                onClaim={activeTab === "new" ? handleClaim : undefined}
                locale={locale}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
