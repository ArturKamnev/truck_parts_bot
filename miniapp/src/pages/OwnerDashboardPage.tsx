import React, { useEffect, useState } from "react";
import { Users, FileText, Activity, Layers, MessageSquare, Radio } from "lucide-react";
import { getOwnerStats, getOwnerTickets, type OwnerStats, type Ticket } from "../api/tickets";
import { TicketCard } from "../components/TicketCard";
import { EmptyState } from "../components/EmptyState";
import { type ApiError } from "../api/client";

interface OwnerDashboardPageProps {
  onSelectTicket: (ticketId: number) => void;
}

export const OwnerDashboardPage: React.FC<OwnerDashboardPageProps> = ({ onSelectTicket }) => {
  const [stats, setStats] = useState<OwnerStats | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

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

  useEffect(() => {
    fetchDashboardData();
  }, []);

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
          SYSTEM OVERVIEW
        </h2>
        <button
          onClick={fetchDashboardData}
          style={{ fontSize: "12px", color: "hsl(var(--accent-hsl))", fontWeight: 600 }}
        >
          Refresh
        </button>
      </div>

      {/* Grid of stats */}
      {loading ? (
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
          title="Failed to load statistics"
          description={error.message}
          actionLabel="Try Again"
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
              <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>CUSTOMERS</span>
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
              <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>OPEN TICKETS</span>
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
              <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>CLAIMED</span>
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
              <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>CLOSED</span>
            </div>
            <span style={{ fontSize: "20px", fontWeight: 700 }}>{stats.closed_tickets}</span>
          </div>
        </div>
      ) : null}

      {/* Placeholders section */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px" }}>
        {/* Manager Overview Card */}
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
            <Activity size={14} style={{ color: "hsl(var(--accent-hsl))" }} />
            <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>MANAGERS STATE</span>
          </div>
          <span style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>Stage 3 Analytics</span>
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
            <span style={{ fontSize: "11px", fontWeight: 600, color: "hsl(var(--text-hint-hsl))" }}>BROADCASTS</span>
          </div>
          <span style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>Stage 3 Control</span>
        </div>
      </div>

      {/* Ticket Logs List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: 700, color: "hsl(var(--text-hint-hsl))", letterSpacing: "0.05em" }}>
          ALL TICKETS LOGS ({tickets.length})
        </h3>

        {loading ? (
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
            title="No tickets in system"
            description="There are no support tickets in the database."
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {tickets.map((ticket) => (
              <TicketCard
                key={ticket.id}
                ticket={ticket}
                showCustomerDetails={true}
                onSelect={onSelectTicket}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
