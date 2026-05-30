import React, { useEffect, useState } from "react";
import { ExternalLink, Bot } from "lucide-react";
import { getCustomerTickets, type Ticket } from "../api/tickets";
import { TicketCard } from "../components/TicketCard";
import { EmptyState } from "../components/EmptyState";
import { type ApiError } from "../api/client";

interface CustomerHomePageProps {
  onSelectTicket: (ticketId: number) => void;
}

export const CustomerHomePage: React.FC<CustomerHomePageProps> = ({ onSelectTicket }) => {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const fetchTickets = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getCustomerTickets();
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
            <h4 style={{ fontSize: "14px", fontWeight: 700 }}>Центр поддержки</h4>
            <span style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>
              История обращений и ИИ-ассистент
            </span>
          </div>
        </div>
        
        <p style={{ fontSize: "13px", color: "hsl(var(--text-hint-hsl))", lineHeight: "1.4", margin: 0 }}>
          Здесь вы можете просматривать историю ваших обращений и переписываться с менеджерами поддержки. Для быстрых ответов используйте вкладку AI Helper.
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
          <span>Открыть бот в Telegram</span>
          <ExternalLink size={14} />
        </a>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ fontSize: "14px", fontWeight: 700, letterSpacing: "0.05em", color: "hsl(var(--text-hint-hsl))" }}>
            MY REQUESTS ({tickets.length})
          </h3>
          {tickets.length > 0 && (
            <button
              onClick={fetchTickets}
              style={{ fontSize: "12px", color: "hsl(var(--accent-hsl))", fontWeight: 600 }}
            >
              Refresh
            </button>
          )}
        </div>

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
            title="Unable to load requests"
            description={error.message}
            actionLabel="Try Again"
            onAction={fetchTickets}
          />
        ) : tickets.length === 0 ? (
          <EmptyState
            title="No support requests found"
            description="You don't have any active support tickets. Return to the Telegram bot chat to open a request if you need support."
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {tickets.map((ticket) => (
              <TicketCard
                key={ticket.id}
                ticket={ticket}
                showCustomerDetails={false}
                onSelect={onSelectTicket}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
