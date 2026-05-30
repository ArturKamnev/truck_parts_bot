import React from "react";
import { Calendar, ChevronRight } from "lucide-react";
import { type Ticket } from "../api/tickets";
import { safeDate } from "../utils/normalization";
import { t } from "../i18n";

interface TicketCardProps {
  ticket: Ticket;
  showCustomerDetails: boolean;
  onSelect: (ticketId: number) => void;
  onClaim?: (ticketId: number) => void;
  locale: string;
}

export const TicketCard: React.FC<TicketCardProps> = ({
  ticket,
  showCustomerDetails,
  onSelect,
  onClaim,
  locale,
}) => {
  const getStatusStyle = (status: string) => {
    switch (status) {
      case "OPEN":
        return { bg: "rgba(75, 181, 67, 0.15)", text: "#4bb543", label: t("chat.status_open", locale) };
      case "CLAIMED":
        return { bg: "rgba(82, 136, 193, 0.15)", text: "#5288c1", label: t("chat.status_claimed", locale) };
      case "CLOSED":
        return { bg: "rgba(112, 132, 153, 0.15)", text: "#708499", label: t("chat.status_closed", locale) };
      default:
        return { bg: "rgba(112, 132, 153, 0.15)", text: "#708499", label: status };
    }
  };

  const statusStyle = getStatusStyle(ticket.status || "UNKNOWN");
  const formattedDate = safeDate(ticket.created_at);


  const customerName = [ticket.customer_first_name, ticket.customer_last_name]
    .filter(Boolean)
    .join(" ") || ticket.customer_username || `User ${ticket.customer_id}`;

  return (
    <div
      onClick={() => onSelect(ticket.id)}
      style={{
        backgroundColor: "hsl(var(--card-bg-hsl))",
        border: "1px solid hsl(var(--border-hsl))",
        borderRadius: "var(--radius-md)",
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        cursor: "pointer",
        transition: "transform 0.15s ease, border-color 0.15s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "hsl(var(--accent-hsl))";
        e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "hsl(var(--border-hsl))";
        e.currentTarget.style.transform = "none";
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "14px", fontWeight: 700, color: "hsl(var(--accent-hsl))" }}>
              Ticket #{ticket.id}
            </span>
            <span
              style={{
                padding: "2px 6px",
                borderRadius: "4px",
                fontSize: "10px",
                fontWeight: 600,
                backgroundColor: statusStyle.bg,
                color: statusStyle.text,
                textTransform: "uppercase",
              }}
            >
              {statusStyle.label}
            </span>
          </div>

          {showCustomerDetails && (
            <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "14px", fontWeight: 500 }}>
              <span style={{ color: "hsl(var(--text-primary-hsl))" }}>{customerName}</span>
              {ticket.customer_username && (
                <span style={{ color: "hsl(var(--text-hint-hsl))", fontSize: "12px" }}>
                  @{ticket.customer_username}
                </span>
              )}
            </div>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: "12px", color: "hsl(var(--text-hint-hsl))", fontSize: "12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <Calendar size={12} />
              <span>{formattedDate}</span>
            </div>
            {ticket.assigned_manager_telegram_id && (
              <span>Mgr ID: {ticket.assigned_manager_telegram_id}</span>
            )}
          </div>
        </div>

        <div style={{ color: "hsl(var(--text-hint-hsl))", marginLeft: "12px" }}>
          <ChevronRight size={20} />
        </div>
      </div>

      {onClaim && ticket.status === "OPEN" && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onClaim(ticket.id);
          }}
          style={{
            padding: "8px 16px",
            backgroundColor: "hsl(var(--accent-hsl))",
            color: "#fff",
            border: "none",
            borderRadius: "var(--radius-sm)",
            fontSize: "13px",
            fontWeight: 600,
            cursor: "pointer",
            transition: "opacity 0.15s ease",
            width: "100%",
            textAlign: "center",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.opacity = "0.9";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.opacity = "1";
          }}
        >
          {t("chat.claim_ticket", locale)}
        </button>
      )}
    </div>
  );
};
