import React, { useEffect, useState } from "react";
import { Inbox, MessageSquare, CheckCircle2 } from "lucide-react";
import { getManagerNewTickets, getManagerActiveTickets, getManagerClosedTickets, claimTicket, type Ticket } from "../api/tickets";
import { TicketCard } from "../components/TicketCard";
import { EmptyState } from "../components/EmptyState";
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const fetchTickets = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const data = activeTab === "new" 
        ? await getManagerNewTickets() 
        : activeTab === "active"
          ? await getManagerActiveTickets()
          : await getManagerClosedTickets();
        
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
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: "12px", fontWeight: 700, letterSpacing: "0.05em", color: "hsl(var(--text-hint-hsl))" }}>
            {activeTab === "new" ? t("manager.unclaimed_queue", locale) : activeTab === "active" ? t("manager.assigned_tickets", locale) : t("manager.closed_chats_list", locale)} ({tickets.length})
          </span>
          <button
            onClick={fetchTickets}
            style={{ fontSize: "12px", color: "hsl(var(--accent-hsl))", fontWeight: 600, background: "none", border: "none", cursor: "pointer" }}
          >
            {t("common.refresh", locale)}
          </button>
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
        ) : tickets.length === 0 ? (
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
            {tickets.map((ticket) => (
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
