import React, { useEffect, useState } from "react";
import { ExternalLink, Bot, CheckCircle2, MessageSquare, PlusCircle, Search, Sparkles, X } from "lucide-react";
import { getCustomerOverview, getCustomerTickets, type CustomerOverview, type Ticket } from "../api/tickets";
import { TicketCard } from "../components/TicketCard";
import { EmptyState } from "../components/EmptyState";
import { BarList, StatCard } from "../components/MiniCharts";
import { type ApiError } from "../api/client";
import { t } from "../i18n";

interface CustomerHomePageProps {
  onSelectTicket: (ticketId: number) => void;
  locale: string;
  setActiveTab?: (tab: string) => void;
}

export const CustomerHomePage: React.FC<CustomerHomePageProps> = ({ onSelectTicket, locale, setActiveTab }) => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [overview, setOverview] = useState<CustomerOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [query, setQuery] = useState("");
  const [showClosed, setShowClosed] = useState(true);

  const fetchTickets = async () => {
    try {
      setLoading(true);
      setError(null);
      const [overviewData, data] = await Promise.all([getCustomerOverview(), getCustomerTickets()]);
      setOverview(overviewData);
      setTickets(data);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTickets();
  }, []);

  const filteredTickets = tickets.filter((ticket) => {
    if (!showClosed && (ticket.status === "CLOSED" || ticket.status === "CANCELLED_BY_CUSTOMER")) return false;
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return true;
    return [ticket.id, ticket.status, ticket.assigned_manager_telegram_id].join(" ").toLowerCase().includes(normalizedQuery);
  });

  return (
    <div
      className="animate-fade-in"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        padding: "16px",
        overflowY: "auto",
        height: "100%",
      }}
      >
        {overview && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "10px" }}>
            <StatCard icon={MessageSquare} label={t("customer.active_chat", locale)} value={overview.active_chats} />
            <StatCard icon={CheckCircle2} label={t("customer.closed_chats", locale)} value={overview.closed_chats} tone="success" />
          </div>
        )}

      {/* Welcome & Information Banner */}
      <div
        style={{
          backgroundColor: "hsl(var(--card-bg-hsl))",
          border: "1px solid hsl(var(--border-hsl))",
          borderRadius: "var(--radius-md)",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "50%",
              backgroundColor: "rgba(82, 136, 193, 0.1)",
              color: "hsl(var(--accent-hsl))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Bot size={18} />
          </div>
          <div>
            <h4 style={{ fontSize: "14px", fontWeight: 700 }}>{t("customer.support_center", locale)}</h4>
            <span style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>
              {t("customer.support_desc", locale)}
            </span>
          </div>
        </div>
        
        <p style={{ fontSize: "13px", color: "hsl(var(--text-hint-hsl))", lineHeight: "1.4", margin: 0 }}>
          {t("customer.support_hint", locale)}
        </p>

        <a
          href="tg://resolve?domain=truckparts_kg_bot"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "6px",
            width: "100%",
            padding: "10px",
            backgroundColor: "hsl(var(--accent-hsl))",
            color: "#fff",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            fontWeight: 600,
            textDecoration: "none",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "hsl(var(--accent-hover-hsl))")}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "hsl(var(--accent-hsl))")}
        >
          <span>{t("common.telegram_bot", locale)}</span>
          <ExternalLink size={14} />
        </a>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "8px" }}>
          <button
            onClick={() => setActiveTab?.("new_chat")}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              padding: "10px",
              backgroundColor: "hsl(var(--accent-hsl))",
              color: "#fff",
              borderRadius: "var(--radius-sm)",
              fontSize: "13px",
              fontWeight: 700,
            }}
          >
            <PlusCircle size={15} />
            {t("customer.create_chat", locale)}
          </button>
          <button
            onClick={() => setActiveTab?.("ai_helper")}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              padding: "10px",
              border: "1px solid hsl(var(--border-hsl))",
              color: "hsl(var(--accent-hsl))",
              borderRadius: "var(--radius-sm)",
              fontSize: "13px",
              fontWeight: 700,
            }}
          >
            <Sparkles size={15} />
            {t("nav.ai_helper", locale)}
          </button>
        </div>
      </div>

      {overview && (
        <div className="premium-card" style={{ padding: "14px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "10px", alignItems: "center" }}>
            <span style={{ fontSize: "12px", fontWeight: 800, color: "hsl(var(--text-hint-hsl))" }}>
              {t("customer.request_mix", locale)}
            </span>
            <span style={{ fontSize: "11px", color: overview.broadcasts_enabled ? "hsl(var(--success-hsl))" : "hsl(var(--text-hint-hsl))" }}>
              {overview.broadcasts_enabled ? t("customer.broadcasts_on", locale) : t("customer.broadcasts_off", locale)}
            </span>
          </div>
          <BarList
            points={overview.tickets_by_status.map((point) => ({
              ...point,
              label: t(`ticket.status_${point.label.toLowerCase()}`, locale),
            }))}
            emptyLabel={t("owner.no_chart_data", locale)}
          />
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, letterSpacing: "0.05em", color: "hsl(var(--text-hint-hsl))" }}>
            {t("customer.my_requests", locale)} ({filteredTickets.length})
          </h3>
          {tickets.length > 0 && (
            <button
              onClick={fetchTickets}
              style={{ fontSize: "12px", color: "hsl(var(--accent-hsl))", fontWeight: 600, background: "none", border: "none", cursor: "pointer" }}
            >
              {t("common.refresh", locale)}
            </button>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", border: "1px solid hsl(var(--border-hsl))", borderRadius: "8px", padding: "9px 10px", background: "hsl(var(--card-bg-hsl))" }}>
          <Search size={15} style={{ color: "hsl(var(--text-hint-hsl))" }} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("customer.search_requests", locale)} style={{ flex: 1, fontSize: "13px" }} />
          {query && (
            <button onClick={() => setQuery("")} title={t("owner.clear_filters", locale)} style={{ color: "hsl(var(--text-hint-hsl))" }}>
              <X size={15} />
            </button>
          )}
        </div>
        <button
          onClick={() => setShowClosed((value) => !value)}
          style={{ alignSelf: "flex-start", border: "1px solid hsl(var(--border-hsl))", borderRadius: "999px", padding: "7px 10px", color: "hsl(var(--text-hint-hsl))", fontSize: "12px", fontWeight: 700 }}
        >
          {showClosed ? t("customer.hide_closed", locale) : t("customer.show_closed", locale)}
        </button>

        {loading ? (
          // Skeletons
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {[1, 2].map((i) => (
              <div
                key={i}
                className="skeleton"
                style={{ height: "78px", width: "100%", borderRadius: "var(--radius-md)" }}
              />
            ))}
          </div>
        ) : error ? (
          <EmptyState
            title={t("customer.load_failed", locale)}
            description={error.message}
            actionLabel={t("common.retry", locale)}
            onAction={fetchTickets}
          />
        ) : filteredTickets.length === 0 ? (
          <EmptyState
            title={t("customer.no_requests", locale)}
            description={t("customer.no_requests_desc", locale)}
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {filteredTickets.map((ticket) => (
              <TicketCard
                key={ticket.id}
                ticket={ticket}
                showCustomerDetails={false}
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
