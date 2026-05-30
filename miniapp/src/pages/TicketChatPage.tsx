import React, { useEffect, useState, useRef } from "react";
import { ArrowLeft, RefreshCw, AlertTriangle, ShieldCheck } from "lucide-react";
import { 
  getCustomerTicketDetails, getCustomerTicketMessages, 
  getManagerTicketDetails, getManagerTicketMessages, 
  claimTicket, closeTicket, sendTicketMessage,
  type Ticket, type TicketMessage 
} from "../api/tickets";
import { ChatBubble } from "../components/ChatBubble";
import { type ApiError } from "../api/client";

interface TicketChatPageProps {
  ticketId: number;
  viewerRole: "customer" | "manager" | "owner";
  onBack: () => void;
}

export const TicketChatPage: React.FC<TicketChatPageProps> = ({
  ticketId,
  viewerRole,
  onBack,
}) => {
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [messages, setMessages] = useState<TicketMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  // Stage 3 interactive states
  const [inputText, setInputText] = useState("");
  const [sending, setSending] = useState(false);
  const [asSupervisor, setAsSupervisor] = useState(false);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  
  const chatEndRef = useRef<HTMLDivElement>(null);

  const loadTicketAndMessages = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      let fetchDetails;
      let fetchMessages;

      if (viewerRole === "customer") {
        fetchDetails = () => getCustomerTicketDetails(ticketId);
        fetchMessages = (limit?: number, after?: number) => getCustomerTicketMessages(ticketId, limit, after);
      } else {
        fetchDetails = () => getManagerTicketDetails(ticketId);
        fetchMessages = (limit?: number, after?: number) => getManagerTicketMessages(ticketId, limit, after);
      }

      const ticketDetails = await fetchDetails();
      setTicket(ticketDetails);

      if (isRefresh && messages.length > 0) {
        // Find highest persisted ID (exclude optimistic/negative IDs)
        const validMsgs = messages.filter(m => m.id > 0);
        const lastId = validMsgs.length > 0 ? validMsgs[validMsgs.length - 1].id : undefined;
        const newMsgs = await fetchMessages(50, lastId);
        if (newMsgs.length > 0) {
          setMessages(prev => {
            const existingIds = new Set(prev.map(m => m.id));
            const uniqueNew = newMsgs.filter(m => !existingIds.has(m.id));
            return [...prev, ...uniqueNew];
          });
        }
      } else {
        const initialMsgs = await fetchMessages(50);
        setMessages(initialMsgs);
      }
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadTicketAndMessages();
  }, [ticketId]);

  // Scroll to bottom when messages load/change
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  // Periodic polling check every 2.5 seconds
  useEffect(() => {
    if (loading || !ticket || ticket.status === "CLOSED") return;

    let intervalId: any = null;

    const poll = async () => {
      const validMsgs = messages.filter(m => m.id > 0);
      const lastId = validMsgs.length > 0 ? validMsgs[validMsgs.length - 1].id : undefined;

      try {
        let fetchMessages;
        if (viewerRole === "customer") {
          fetchMessages = (limit?: number, after?: number) => getCustomerTicketMessages(ticketId, limit, after);
        } else {
          fetchMessages = (limit?: number, after?: number) => getManagerTicketMessages(ticketId, limit, after);
        }

        const newMsgs = await fetchMessages(50, lastId);
        if (newMsgs.length > 0) {
          setMessages(prev => {
            const existingIds = new Set(prev.map(m => m.id));
            const uniqueNew = newMsgs.filter(m => !existingIds.has(m.id));
            if (uniqueNew.length === 0) return prev;
            return [...prev, ...uniqueNew];
          });
        }
      } catch (err) {
        console.error("Polling fetch failed:", err);
      }
    };

    const startPolling = () => {
      if (document.hidden) return;
      intervalId = setInterval(poll, 2500);
    };

    const stopPolling = () => {
      if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const handleVisibility = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        startPolling();
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);
    startPolling();

    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [ticketId, ticket, messages, loading]);

  // Handle claiming ticket
  const handleClaim = async () => {
    try {
      setLoading(true);
      const updated = await claimTicket(ticketId);
      setTicket(updated);
      await loadTicketAndMessages(false);
    } catch (err) {
      alert((err as ApiError).message || "Failed to claim ticket.");
    } finally {
      setLoading(false);
    }
  };

  // Handle closing ticket
  const handleCloseTicket = async () => {
    try {
      setShowCloseConfirm(false);
      setLoading(true);
      const updated = await closeTicket(ticketId, asSupervisor);
      setTicket(updated);
      await loadTicketAndMessages(false);
    } catch (err) {
      alert((err as ApiError).message || "Failed to close ticket.");
    } finally {
      setLoading(false);
    }
  };

  // Handle sending a message
  const handleSend = async (textToSend?: string) => {
    const content = (textToSend || inputText).trim();
    if (!content || sending) return;

    // Reset input text if we are sending a new message
    if (!textToSend) {
      setInputText("");
    }

    setSending(true);

    // Create optimistic message object
    const tempMsgId = -Date.now();
    const tempMsg: TicketMessage = {
      id: tempMsgId,
      ticketId,
      senderType: viewerRole === "owner" ? "owner" : "manager",
      contentType: "text",
      textPreview: content,
      captionPreview: null,
      createdAt: new Date().toISOString(),
      hasMedia: false,
    };

    // Optimistically append message
    setMessages(prev => [...prev, tempMsg]);

    try {
      const persisted = await sendTicketMessage(ticketId, content, asSupervisor);
      // Replace optimistic placeholder with backend-persisted object
      setMessages(prev => prev.map(m => m.id === tempMsgId ? persisted : m));
    } catch (err) {
      // Mark deliveryStatus as FAILED
      setMessages(prev => prev.map(m => m.id === tempMsgId ? { ...m, deliveryStatus: "FAILED" } : m));
    } finally {
      setSending(false);
    }
  };

  // Retry sending a failed message
  const handleRetrySend = async (failedMsg: TicketMessage) => {
    if (!failedMsg.textPreview) return;
    
    // Remove the failed message from the local state list
    setMessages(prev => prev.filter(m => m.id !== failedMsg.id));
    
    // Resend it
    await handleSend(failedMsg.textPreview);
  };

  const customerName = ticket 
    ? [ticket.customer_first_name, ticket.customer_last_name].filter(Boolean).join(" ") || ticket.customer_username || `User ${ticket.customer_id}`
    : "";

  return (
    <div
      className="animate-fade-in"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        backgroundColor: "hsl(var(--bg-secondary-hsl))",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Sub-header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 12px",
          backgroundColor: "hsl(var(--card-bg-hsl))",
          borderBottom: "1px solid hsl(var(--border-hsl))",
        }}
      >
        <button
          onClick={onBack}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            fontSize: "14px",
            fontWeight: 600,
            color: "hsl(var(--accent-hsl))",
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: 0,
          }}
        >
          <ArrowLeft size={18} />
          Back
        </button>

        <span style={{ fontSize: "14px", fontWeight: 700 }}>
          {loading ? "Loading chat..." : `Ticket #${ticketId}`}
        </span>

        {viewerRole !== "customer" && ticket && (ticket.status === "OPEN" || ticket.status === "CLAIMED") && (
          (viewerRole === "manager" && ticket.assigned_manager_telegram_id === ticket.assigned_manager_telegram_id) || 
          (viewerRole === "owner" && asSupervisor)
        ) ? (
          <button
            onClick={() => setShowCloseConfirm(true)}
            style={{
              padding: "4px 8px",
              backgroundColor: "rgba(255, 77, 77, 0.15)",
              color: "#ff4d4d",
              border: "none",
              borderRadius: "4px",
              fontSize: "12px",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Close
          </button>
        ) : (
          <button
            onClick={() => loadTicketAndMessages(true)}
            disabled={loading || refreshing}
            style={{
              color: "hsl(var(--accent-hsl))",
              display: "flex",
              alignItems: "center",
              opacity: loading || refreshing ? 0.5 : 1,
              background: "none",
              border: "none",
              cursor: "pointer",
            }}
          >
            <RefreshCw size={16} className={refreshing ? "animate-pulse-slow" : ""} />
          </button>
        )}
      </div>

      {/* Ticket Details Panel */}
      {ticket && (
        <div
          style={{
            padding: "10px 16px",
            backgroundColor: "rgba(82, 136, 193, 0.04)",
            borderBottom: "1px solid hsl(var(--border-hsl))",
            display: "flex",
            flexDirection: "column",
            gap: "6px",
            fontSize: "12px",
            color: "hsl(var(--text-hint-hsl))",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <div>
              Client: <span style={{ color: "#fff", fontWeight: 500 }}>{customerName}</span>
            </div>
            <div>
              Status: <span style={{ color: "hsl(var(--accent-hsl))", fontWeight: 600, textTransform: "uppercase" }}>{ticket.status}</span>
            </div>
          </div>

          {/* Owner Supervisor toggle */}
          {viewerRole === "owner" && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                marginTop: "4px",
                padding: "6px 10px",
                backgroundColor: asSupervisor ? "rgba(82, 136, 193, 0.12)" : "rgba(255, 255, 255, 0.03)",
                borderRadius: "6px",
                border: "1px solid " + (asSupervisor ? "rgba(82, 136, 193, 0.25)" : "hsl(var(--border-hsl))"),
                transition: "all 0.15s ease",
              }}
            >
              <input
                type="checkbox"
                id="supervisor-toggle"
                checked={asSupervisor}
                onChange={(e) => setAsSupervisor(e.target.checked)}
                style={{ cursor: "pointer" }}
              />
              <label
                htmlFor="supervisor-toggle"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  fontWeight: 600,
                  fontSize: "11px",
                  color: asSupervisor ? "hsl(var(--accent-hsl))" : "hsl(var(--text-hint-hsl))",
                  cursor: "pointer",
                }}
              >
                <ShieldCheck size={14} />
                Act as Supervisor (Enables Messaging & Close Actions)
              </label>
            </div>
          )}
        </div>
      )}

      {/* Message Feed Area */}
      <div
        style={{
          flex: 1,
          padding: "16px",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {loading && messages.length === 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px", width: "100%" }}>
            <div className="skeleton" style={{ height: "42px", width: "60%", borderRadius: "14px" }} />
            <div className="skeleton" style={{ height: "60px", width: "50%", alignSelf: "flex-end", borderRadius: "14px" }} />
            <div className="skeleton" style={{ height: "42px", width: "70%", borderRadius: "14px" }} />
          </div>
        ) : error ? (
          <div
            style={{
              margin: "auto",
              textAlign: "center",
              padding: "24px",
              color: "hsl(var(--text-hint-hsl))",
            }}
          >
            <p style={{ marginBottom: "12px" }}>{error.message}</p>
            <button
              onClick={() => loadTicketAndMessages()}
              style={{
                fontSize: "13px",
                color: "hsl(var(--accent-hsl))",
                fontWeight: 600,
                background: "none",
                border: "none",
                cursor: "pointer",
              }}
            >
              Retry Load
            </button>
          </div>
        ) : messages.length === 0 ? (
          <div style={{ margin: "auto", textAlign: "center", color: "hsl(var(--text-hint-hsl))" }}>
            <p style={{ fontSize: "14px" }}>No messages in this chat history.</p>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <ChatBubble 
                key={msg.id} 
                message={msg} 
                viewerRole={viewerRole} 
                onRetry={handleRetrySend}
              />
            ))}
            <div ref={chatEndRef} />
          </>
        )}
      </div>

      {/* Input Composer / Claim panel */}
      {viewerRole !== "customer" && ticket && (
        <div
          style={{
            padding: "12px 16px calc(12px + var(--sab))",
            backgroundColor: "hsl(var(--card-bg-hsl))",
            borderTop: "1px solid hsl(var(--border-hsl))",
          }}
        >
          {ticket.status === "CLOSED" ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", color: "hsl(var(--text-hint-hsl))", fontSize: "13px" }}>
              <AlertTriangle size={16} />
              <span>Ticket is closed. Composer disabled.</span>
            </div>
          ) : viewerRole === "owner" && !asSupervisor ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", color: "hsl(var(--text-hint-hsl))", fontSize: "13px" }}>
              <span>You are in read-only mode. Enable Supervisor Mode above to write.</span>
            </div>
          ) : ticket.status === "OPEN" ? (
            <button
              onClick={handleClaim}
              style={{
                width: "100%",
                padding: "12px",
                backgroundColor: "hsl(var(--accent-hsl))",
                color: "#fff",
                border: "none",
                borderRadius: "var(--radius-md)",
                fontWeight: 600,
                fontSize: "14px",
                cursor: "pointer",
              }}
            >
              Claim Ticket to Start Chatting
            </button>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              style={{ display: "flex", gap: "8px", alignItems: "center" }}
            >
              <input
                type="text"
                className="composer-input"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                disabled={sending}
                placeholder="Type your message to customer..."
                style={{
                  flex: 1,
                  padding: "10px 14px",
                  borderRadius: "18px",
                  backgroundColor: "hsl(var(--bg-secondary-hsl))",
                  border: "1px solid hsl(var(--border-hsl))",
                  color: "#fff",
                  fontSize: "14px",
                  outline: "none",
                }}
              />
              <button
                type="submit"
                className="composer-send-btn"
                disabled={sending || !inputText.trim()}
                style={{
                  padding: "8px 16px",
                  borderRadius: "18px",
                  backgroundColor: "hsl(var(--accent-hsl))",
                  color: "#fff",
                  border: "none",
                  fontWeight: 600,
                  fontSize: "13px",
                  cursor: "pointer",
                  opacity: sending || !inputText.trim() ? 0.5 : 1,
                }}
              >
                Send
              </button>
            </form>
          )}
        </div>
      )}

      {/* Read-Only Status Bar for Customer */}
      {viewerRole === "customer" && (
        <div
          style={{
            padding: "12px 16px",
            backgroundColor: "hsl(var(--card-bg-hsl))",
            borderTop: "1px solid hsl(var(--border-hsl))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            fontSize: "13px",
            color: "hsl(var(--warning-hsl))",
            paddingBottom: "calc(12px + var(--sab))",
          }}
        >
          <AlertTriangle size={16} />
          <span>Please use your Telegram bot window to send messages.</span>
        </div>
      )}

      {/* Sliding Close Confirmation Sheet */}
      {showCloseConfirm && (
        <div
          style={{
            position: "absolute",
            top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "flex-end",
            zIndex: 100,
          }}
        >
          <div
            className="animate-slide-up"
            style={{
              backgroundColor: "hsl(var(--card-bg-hsl))",
              borderTopLeftRadius: "16px",
              borderTopRightRadius: "16px",
              padding: "24px 16px calc(24px + var(--sab))",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
              boxShadow: "0 -4px 20px rgba(0, 0, 0, 0.5)",
            }}
          >
            <div style={{ textAlign: "center" }}>
              <h3 style={{ fontSize: "16px", fontWeight: 700, margin: "0 0 8px 0", color: "#fff" }}>Close Ticket?</h3>
              <p style={{ fontSize: "13px", color: "hsl(var(--text-hint-hsl))", margin: 0 }}>
                This will return the customer to the AI helper chat and close this support thread.
              </p>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <button
                onClick={handleCloseTicket}
                style={{
                  padding: "12px",
                  backgroundColor: "#ff4d4d",
                  color: "#fff",
                  border: "none",
                  borderRadius: "var(--radius-md)",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
                }}
              >
                Yes, Close Ticket
              </button>
              <button
                onClick={() => setShowCloseConfirm(false)}
                style={{
                  padding: "12px",
                  backgroundColor: "rgba(255, 255, 255, 0.08)",
                  color: "hsl(var(--text-primary-hsl))",
                  border: "none",
                  borderRadius: "var(--radius-md)",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
