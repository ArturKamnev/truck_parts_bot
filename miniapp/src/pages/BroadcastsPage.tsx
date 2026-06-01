import React, { useEffect, useMemo, useState } from "react";
import { CheckCircle2, History, Radio, RefreshCw, Send, X } from "lucide-react";
import {
  cancelBroadcast,
  createBroadcastDraft,
  getOwnerBroadcasts,
  previewBroadcast,
  sendBroadcast,
  setBroadcastButtons,
  setBroadcastContent,
  type Broadcast,
  type BroadcastPreview,
} from "../api/tickets";
import { type ApiError } from "../api/client";
import { t } from "../i18n";

interface BroadcastsPageProps {
  locale: string;
}

const buttonOptions = ["none", "instagram", "site", "both"] as const;

export const BroadcastsPage: React.FC<BroadcastsPageProps> = ({ locale }) => {
  const [history, setHistory] = useState<Broadcast[]>([]);
  const [draft, setDraft] = useState<Broadcast | null>(null);
  const [preview, setPreview] = useState<BroadcastPreview | null>(null);
  const [text, setText] = useState("");
  const [buttonSelection, setButtonSelection] = useState("none");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canPreview = useMemo(() => text.trim().length > 0 && !submitting, [text, submitting]);

  const loadHistory = async () => {
    try {
      setLoading(true);
      setError(null);
      setHistory(await getOwnerBroadcasts());
    } catch (err) {
      setError((err as ApiError).message || t("broadcast.error_load", locale));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const handleCreatePreview = async () => {
    if (!canPreview) return;
    try {
      setSubmitting(true);
      setError(null);
      setSuccess(null);
      const activeDraft = draft || await createBroadcastDraft();
      const contentDraft = await setBroadcastContent(activeDraft.id, text.trim());
      const readyDraft = await setBroadcastButtons(contentDraft.id, buttonSelection);
      const nextPreview = await previewBroadcast(readyDraft.id);
      setDraft(readyDraft);
      setPreview(nextPreview);
    } catch (err) {
      setError((err as ApiError).message || t("broadcast.error_preview", locale));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSend = async () => {
    if (!draft) return;
    try {
      setSubmitting(true);
      setError(null);
      await sendBroadcast(draft.id);
      setSuccess(t("broadcast.sent", locale));
      setDraft(null);
      setPreview(null);
      setText("");
      setButtonSelection("none");
      await loadHistory();
    } catch (err) {
      setError((err as ApiError).message || t("broadcast.error_send", locale));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (draft) {
      try {
        await cancelBroadcast(draft.id);
      } catch (err) {
        if (import.meta.env.DEV) console.warn("[broadcast] Cancel draft failed", err);
      }
    }
    setDraft(null);
    setPreview(null);
    setText("");
    setButtonSelection("none");
    setError(null);
  };

  const statusLabel = (status: string) => {
    const normalized = status.toUpperCase();
    return t(`broadcast.status_${normalized.toLowerCase()}`, locale);
  };

  return (
    <div style={{ height: "100%", overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: "16px", paddingBottom: "96px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "20px", fontWeight: 800, color: "#fff" }}>{t("broadcast.title", locale)}</h2>
          <p style={{ margin: "4px 0 0", fontSize: "13px", color: "hsl(var(--text-hint-hsl))" }}>
            {t("broadcast.subtitle", locale)}
          </p>
        </div>
        <button
          onClick={loadHistory}
          disabled={loading}
          title={t("common.refresh", locale)}
          style={{ border: "none", background: "transparent", color: "hsl(var(--accent-hsl))", cursor: "pointer", padding: "8px" }}
        >
          <RefreshCw size={18} className={loading ? "animate-pulse-slow" : ""} />
        </button>
      </div>

      {error && (
        <div style={{ border: "1px solid hsl(var(--danger-hsl))", background: "rgba(255,77,77,0.08)", color: "#ff8a8a", borderRadius: "8px", padding: "12px", fontSize: "13px" }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ border: "1px solid hsl(var(--success-hsl))", background: "rgba(46,204,113,0.08)", color: "hsl(var(--success-hsl))", borderRadius: "8px", padding: "12px", fontSize: "13px", display: "flex", gap: "8px", alignItems: "center" }}>
          <CheckCircle2 size={16} /> {success}
        </div>
      )}

      <section style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Radio size={16} style={{ color: "hsl(var(--accent-hsl))" }} />
          <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "#fff" }}>{t("broadcast.create", locale)}</h3>
        </div>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          disabled={submitting}
          placeholder={t("broadcast.text_placeholder", locale)}
          style={{ minHeight: "132px", resize: "vertical", borderRadius: "8px", border: "1px solid hsl(var(--border-hsl))", background: "hsl(var(--card-bg-hsl))", color: "#fff", padding: "12px", fontSize: "14px", lineHeight: 1.5, outline: "none" }}
        />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "8px" }}>
          {buttonOptions.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setButtonSelection(option)}
              disabled={submitting}
              style={{ padding: "10px", borderRadius: "8px", border: buttonSelection === option ? "1px solid hsl(var(--accent-hsl))" : "1px solid hsl(var(--border-hsl))", background: buttonSelection === option ? "rgba(82,136,193,0.14)" : "rgba(255,255,255,0.03)", color: buttonSelection === option ? "hsl(var(--accent-hsl))" : "#fff", fontSize: "12px", fontWeight: 700, cursor: "pointer" }}
            >
              {t(`broadcast.button_${option}`, locale)}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={handleCreatePreview}
            disabled={!canPreview}
            style={{ flex: 1, padding: "12px", borderRadius: "8px", border: "none", background: "hsl(var(--accent-hsl))", color: "#fff", fontWeight: 700, cursor: canPreview ? "pointer" : "not-allowed", opacity: canPreview ? 1 : 0.5 }}
          >
            {submitting ? t("common.saving", locale) : t("broadcast.preview", locale)}
          </button>
          {(draft || preview) && (
            <button
              onClick={handleCancel}
              disabled={submitting}
              title={t("common.cancel", locale)}
              style={{ width: "44px", borderRadius: "8px", border: "1px solid hsl(var(--border-hsl))", background: "rgba(255,255,255,0.04)", color: "#fff", cursor: "pointer" }}
            >
              <X size={18} />
            </button>
          )}
        </div>
      </section>

      {preview && (
        <section style={{ border: "1px solid hsl(var(--border-hsl))", background: "hsl(var(--card-bg-hsl))", borderRadius: "8px", padding: "14px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <h3 style={{ margin: 0, fontSize: "15px", color: "#fff" }}>{t("broadcast.preview_title", locale)}</h3>
          <div style={{ whiteSpace: "pre-wrap", color: "#fff", fontSize: "14px", lineHeight: 1.5 }}>{preview.content_preview}</div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>
            <span>{t("broadcast.recipients", locale)}</span>
            <b style={{ color: "#fff" }}>{preview.eligible_recipient_count}</b>
          </div>
          <button
            onClick={handleSend}
            disabled={submitting}
            style={{ padding: "12px", borderRadius: "8px", border: "none", background: "hsl(var(--success-hsl))", color: "#fff", fontWeight: 800, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
          >
            <Send size={16} /> {t("broadcast.confirm_send", locale)}
          </button>
        </section>
      )}

      <section style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <History size={16} style={{ color: "hsl(var(--accent-hsl))" }} />
          <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "#fff" }}>{t("broadcast.history", locale)}</h3>
        </div>
        {loading && history.length === 0 ? (
          <div className="skeleton" style={{ height: "96px", borderRadius: "8px" }} />
        ) : history.length === 0 ? (
          <div style={{ color: "hsl(var(--text-hint-hsl))", fontSize: "13px", padding: "16px", textAlign: "center" }}>
            {t("broadcast.empty", locale)}
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {history.map((item) => (
              <div key={item.id} style={{ border: "1px solid hsl(var(--border-hsl))", background: "rgba(255,255,255,0.02)", borderRadius: "8px", padding: "12px", display: "flex", flexDirection: "column", gap: "6px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: "8px", alignItems: "center" }}>
                  <b style={{ color: "hsl(var(--accent-hsl))", fontSize: "13px" }}>
                    {t("broadcast.item_title", locale).replace("{id}", String(item.id))}
                  </b>
                  <span style={{ color: "hsl(var(--text-hint-hsl))", fontSize: "10px", fontWeight: 700 }}>
                    {statusLabel(item.status)}
                  </span>
                </div>
                {item.content_preview && (
                  <span style={{ color: "#fff", fontSize: "12px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {item.content_preview}
                  </span>
                )}
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", color: "hsl(var(--text-hint-hsl))", fontSize: "11px" }}>
                  <span>{t("broadcast.recipients", locale)}: <b>{item.recipient_count}</b></span>
                  <span>{t("broadcast.delivered", locale)}: <b style={{ color: "hsl(var(--success-hsl))" }}>{item.delivered_count}</b></span>
                  <span>{t("broadcast.failed", locale)}: <b>{item.failed_count}</b></span>
                  <span>{t("broadcast.blocked", locale)}: <b>{item.blocked_count}</b></span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
