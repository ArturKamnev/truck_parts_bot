import React, { useEffect, useState, useRef } from "react";
import { Send, Sparkles, RefreshCw, AlertTriangle } from "lucide-react";
import { getAIChatHistory, sendAIChatMessage, type AIMessage } from "../api/tickets";
import { type ApiError } from "../api/client";
import { safeTime } from "../utils/normalization";

interface AIChatPageProps {}

export const AIChatPage: React.FC<AIChatPageProps> = () => {
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  const loadHistory = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      const history = await getAIChatHistory();
      setMessages(history);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const content = inputText.trim();
    if (!content || sending) return;

    setInputText("");
    setSending(true);

    const tempUserMsg: AIMessage = {
      id: -Date.now(),
      role: "user",
      content,
      model_id: null,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await sendAIChatMessage(content);
      const tempAssistantMsg: AIMessage = {
        id: -Date.now() - 1,
        role: "assistant",
        content: res.response,
        model_id: res.model_id,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempAssistantMsg]);
    } catch (err) {
      const errorMsg: AIMessage = {
        id: -Date.now() - 2,
        role: "assistant",
        content: "Извините, не удалось получить ответ от ИИ. Попробуйте еще раз.",
        model_id: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        backgroundColor: "hsl(var(--bg-secondary-hsl))",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          backgroundColor: "hsl(var(--card-bg-hsl))",
          borderBottom: "1px solid hsl(var(--border-hsl))",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "50%",
              backgroundColor: "rgba(82, 136, 193, 0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "hsl(var(--accent-hsl))",
            }}
          >
            <Sparkles size={18} />
          </div>
          <div>
            <h2 style={{ fontSize: "15px", fontWeight: 700, margin: 0, color: "#fff" }}>
              AI Support Helper
            </h2>
            <span style={{ fontSize: "11px", color: "hsl(var(--text-hint-hsl))" }}>
              Powered by LLM
            </span>
          </div>
        </div>

        <button
          onClick={() => loadHistory(true)}
          disabled={loading || refreshing}
          style={{
            color: "hsl(var(--accent-hsl))",
            background: "none",
            border: "none",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            opacity: loading || refreshing ? 0.5 : 1,
          }}
        >
          <RefreshCw size={16} className={refreshing ? "animate-pulse-slow" : ""} />
        </button>
      </div>

      {/* Verification Warning */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: "8px",
          padding: "10px 16px",
          backgroundColor: "rgba(255, 165, 0, 0.08)",
          borderBottom: "1px solid rgba(255, 165, 0, 0.15)",
          color: "hsl(var(--warning-hsl))",
          fontSize: "12px",
          lineHeight: "1.4",
        }}
      >
        <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: "1px" }} />
        <span>
          <strong>Внимание:</strong> ИИ-помощник может ошибаться и не обладает актуальной информацией об остатках на складе. Всегда проверяйте важные ответы.
        </span>
      </div>

      {/* Messages Feed */}
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
        {loading && messages.length === 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px", width: "100%" }}>
            <div className="skeleton" style={{ height: "40px", width: "60%", borderRadius: "14px" }} />
            <div className="skeleton" style={{ height: "50px", width: "50%", alignSelf: "flex-end", borderRadius: "14px" }} />
            <div className="skeleton" style={{ height: "45px", width: "65%", borderRadius: "14px" }} />
          </div>
        ) : error ? (
          <div style={{ margin: "auto", textAlign: "center", padding: "24px", color: "hsl(var(--text-hint-hsl))" }}>
            <p style={{ marginBottom: "12px" }}>{error.message || "Ошибка загрузки истории"}</p>
            <button
              onClick={() => loadHistory()}
              style={{
                fontSize: "13px",
                color: "hsl(var(--accent-hsl))",
                fontWeight: 600,
                background: "none",
                border: "none",
                cursor: "pointer",
              }}
            >
              Повторить
            </button>
          </div>
        ) : messages.length === 0 ? (
          <div style={{ margin: "auto", textAlign: "center", color: "hsl(var(--text-hint-hsl))", maxWidth: "250px" }}>
            <Sparkles size={32} style={{ color: "hsl(var(--accent-hsl))", opacity: 0.5, marginBottom: "12px" }} />
            <p style={{ fontSize: "14px", margin: 0 }}>
              Спросите меня о компании, её услугах или правилах работы. Я помогу найти ответ!
            </p>
          </div>
        ) : (
          <>
            {messages.map((msg) => {
              const isOutgoing = msg.role === "user";
              const formattedTime = safeTime(msg.created_at);

              return (
                <div
                  key={msg.id}
                  style={{
                    display: "flex",
                    justifyContent: isOutgoing ? "flex-end" : "flex-start",
                    width: "100%",
                  }}
                >
                  <div
                    style={{
                      maxWidth: "75%",
                      borderRadius: "14px",
                      padding: "8px 12px",
                      backgroundColor: isOutgoing ? "hsl(var(--bubble-out-hsl))" : "hsl(var(--bubble-in-hsl))",
                      color: "#fff",
                      borderTopRightRadius: isOutgoing ? "2px" : "14px",
                      borderTopLeftRadius: !isOutgoing ? "2px" : "14px",
                      boxShadow: "var(--shadow-sm)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "4px",
                    }}
                  >
                    {!isOutgoing && (
                      <span style={{ fontSize: "9px", fontWeight: 700, color: "hsl(var(--accent-hsl))", marginBottom: "2px" }}>
                        AI ASSISTANT
                      </span>
                    )}
                    <span style={{ fontSize: "14px", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                      {msg.content}
                    </span>
                    <div style={{ alignSelf: "flex-end", display: "flex", alignItems: "center", gap: "4px" }}>
                      {msg.model_id && (
                        <span style={{ fontSize: "8px", opacity: 0.4 }} title={msg.model_id}>
                          ai
                        </span>
                      )}
                      <span style={{ fontSize: "9px", color: "rgba(255, 255, 255, 0.4)" }}>
                        {formattedTime}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={chatEndRef} />
          </>
        )}
      </div>

      {/* Composer Input */}
      <div
        style={{
          padding: "12px 16px calc(12px + var(--sab))",
          backgroundColor: "hsl(var(--card-bg-hsl))",
          borderTop: "1px solid hsl(var(--border-hsl))",
        }}
      >
        <form onSubmit={handleSend} style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={sending || loading}
            placeholder={sending ? "AI думает..." : "Спросить ИИ-помощника..."}
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
            disabled={sending || !inputText.trim() || loading}
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "50%",
              backgroundColor: "hsl(var(--accent-hsl))",
              color: "#fff",
              border: "none",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              opacity: sending || !inputText.trim() || loading ? 0.5 : 1,
              flexShrink: 0,
            }}
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
};
