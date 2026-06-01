import React, { useEffect, useState } from "react";
import { Download, Image, Volume2, Video, FileText } from "lucide-react";
import { type TicketMessage } from "../api/tickets";
import { API_BASE_URL, getStoredToken } from "../api/client";
import { safeTime } from "../utils/normalization";
import { t } from "../i18n";

interface ChatBubbleProps {
  message: TicketMessage;
  viewerRole: "customer" | "manager" | "owner" | "co_owner";
  onRetry?: (msg: TicketMessage) => void;
  locale: string;
}

export const ChatBubble: React.FC<ChatBubbleProps> = ({ message, viewerRole, onRetry, locale }) => {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  // Determine alignment
  // If customer is viewing: customer messages are on the right, manager/system on the left.
  // If manager/owner is viewing: manager/system are on the right, customer on the left.
  const isSystem = message.senderType === "system";
  let isOutgoing = false;

  if (viewerRole === "customer") {
    isOutgoing = message.senderType === "customer";
  } else {
    isOutgoing = message.senderType === "manager" || message.senderType === "owner";
  }

  const getMediaIcon = (type: string) => {
    switch (type) {
      case "photo":
        return <Image size={16} />;
      case "voice":
        return <Volume2 size={16} />;
      case "video":
        return <Video size={16} />;
      default:
        return <FileText size={16} />;
    }
  };

  const formattedTime = safeTime(message.createdAt);

  useEffect(() => {
    if (!message.downloadUrl || !message.mimeType?.startsWith("image/")) return;
    let active = true;
    let url: string | null = null;
    const loadPreview = async () => {
      const token = getStoredToken();
      const response = await fetch(`${API_BASE_URL}${message.downloadUrl}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!response.ok) return;
      const blob = await response.blob();
      if (!active) return;
      url = URL.createObjectURL(blob);
      setObjectUrl(url);
    };
    loadPreview().catch(() => undefined);
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
      setObjectUrl(null);
    };
  }, [message.downloadUrl, message.mimeType]);

  const handleDownload = async () => {
    if (!message.downloadUrl) return;
    const token = getStoredToken();
    const response = await fetch(`${API_BASE_URL}${message.downloadUrl}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!response.ok) return;
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = message.fileName || "attachment";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  if (isSystem) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          margin: "8px 0",
          fontSize: "12px",
          color: "hsl(var(--text-hint-hsl))",
        }}
      >
        <span
          style={{
            backgroundColor: "rgba(112, 132, 153, 0.08)",
            padding: "4px 10px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid rgba(112, 132, 153, 0.12)",
          }}
        >
          {message.textPreview} • {formattedTime}
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        justifyContent: isOutgoing ? "flex-end" : "flex-start",
        margin: "6px 0",
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
        {/* Sender Label for Managers viewing Client messages */}
        {!isOutgoing && viewerRole !== "customer" && (
          <span style={{ fontSize: "10px", fontWeight: 600, color: "rgba(255, 255, 255, 0.5)", marginBottom: "2px" }}>
            {t("chat.client_label", locale)}
          </span>
        )}
        {!isOutgoing && viewerRole === "customer" && (
          <span style={{ fontSize: "10px", fontWeight: 600, color: "hsl(var(--accent-hsl))", marginBottom: "2px" }}>
            {t("chat.support_staff_label", locale)}
          </span>
        )}

        {/* Message Content */}
        {message.hasMedia ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {objectUrl && (
              <img
                src={objectUrl}
                alt={message.fileName || t("chat.media_photo", locale)}
                style={{
                  maxWidth: "220px",
                  maxHeight: "220px",
                  borderRadius: "8px",
                  objectFit: "cover",
                }}
              />
            )}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "4px",
                padding: "8px",
                backgroundColor: "rgba(0, 0, 0, 0.15)",
                borderRadius: "var(--radius-sm)",
                fontSize: "13px",
                color: "rgba(255, 255, 255, 0.8)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                {getMediaIcon(message.contentType)}
                <span style={{ fontWeight: 600, textTransform: "capitalize" }}>
                  {message.contentType === "photo" ? t("chat.media_photo", locale) :
                   message.contentType === "video" ? t("chat.media_video", locale) :
                   message.contentType === "voice" ? t("chat.media_voice", locale) :
                   message.contentType === "audio" ? t("chat.media_audio", locale) : t("chat.media_document", locale)}
                </span>
              </div>
              <span style={{ fontSize: "11px", opacity: 0.7 }}>
                {message.fileName || t("chat.media_hint", locale)}
              </span>
              {message.downloadUrl && (
                <button
                  type="button"
                  onClick={handleDownload}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    width: "fit-content",
                    marginTop: "2px",
                    padding: "5px 8px",
                    border: "1px solid rgba(255,255,255,0.14)",
                    borderRadius: "6px",
                    background: "rgba(255,255,255,0.08)",
                    color: "#fff",
                    fontSize: "11px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  <Download size={13} />
                  {t("chat.download_file", locale)}
                </button>
              )}
            </div>
            {message.captionPreview && (
              <span style={{ fontSize: "14px", whiteSpace: "pre-wrap" }}>{message.captionPreview}</span>
            )}
          </div>
        ) : (
          <span style={{ fontSize: "14px", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {message.textPreview}
          </span>
        )}

        {/* Timestamp & Delivery status */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            alignSelf: "flex-end",
            marginTop: "2px",
          }}
        >
          {message.deliveryStatus === "FAILED" && (
            <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <span style={{ fontSize: "9px", color: "#ff4d4d", fontWeight: 700, letterSpacing: "0.03em" }}>
                {t("chat.delivery_failed", locale)}
              </span>
              {onRetry && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRetry(message);
                  }}
                  style={{
                    background: "none",
                    border: "none",
                    color: "hsl(var(--accent-hsl))",
                    fontSize: "9px",
                    fontWeight: 700,
                    cursor: "pointer",
                    textDecoration: "underline",
                    padding: 0,
                    margin: 0,
                  }}
                >
                  {t("chat.retry_send", locale)}
                </button>
              )}
            </div>
          )}
          {message.id < 0 && (
            <span style={{ fontSize: "9px", opacity: 0.6, fontStyle: "italic" }}>
              {t("chat.sending", locale)}
            </span>
          )}
          <span
            style={{
              fontSize: "10px",
              color: "rgba(255, 255, 255, 0.4)",
            }}
          >
            {formattedTime}
          </span>
        </div>
      </div>
    </div>
  );
};
