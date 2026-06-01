import React, { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, History, Paperclip, Radio, RefreshCw, Send, X } from "lucide-react";
import {
  cancelBroadcast,
  createBroadcastDraft,
  getOwnerBroadcasts,
  previewBroadcast,
  sendBroadcast,
  setBroadcastAttachment,
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
type BroadcastFlowState =
  | "composer"
  | "saving"
  | "preview_loading"
  | "validation_error"
  | "preview_ready"
  | "sending"
  | "sent"
  | "failed"
  | "cancelled";

export const BroadcastsPage: React.FC<BroadcastsPageProps> = ({ locale }) => {
  const [history, setHistory] = useState<Broadcast[]>([]);
  const [draft, setDraft] = useState<Broadcast | null>(null);
  const [preview, setPreview] = useState<BroadcastPreview | null>(null);
  const [text, setText] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [buttonSelection, setButtonSelection] = useState("none");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const [flowState, setFlowState] = useState<BroadcastFlowState>("composer");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canPreview = useMemo(() => (text.trim().length > 0 || attachment !== null) && !submitting, [text, attachment, submitting]);

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

  const broadcastErrorMessage = (err: unknown, fallbackKey: string) => {
    const apiError = err as ApiError;
    if (apiError.message === "Broadcast request timed out") {
      return t("broadcast.error_timeout", locale);
    }
    return apiError.message || t(fallbackKey, locale);
  };

  const handleCreatePreview = async () => {
    if (!canPreview || submittingRef.current) return;
    if (text.trim().length === 0 && attachment === null) {
      setFlowState("validation_error");
      setError(t("broadcast.error_content_required", locale));
      return;
    }
    try {
      submittingRef.current = true;
      setSubmitting(true);
      setFlowState("saving");
      setError(null);
      setSuccess(null);
      const activeDraft = draft || await createBroadcastDraft();
      setDraft(activeDraft);
      const contentDraft = attachment
        ? await setBroadcastAttachment(activeDraft.id, attachment, text.trim())
        : await setBroadcastContent(activeDraft.id, text.trim());
      setDraft(contentDraft);
      const readyDraft = await setBroadcastButtons(contentDraft.id, buttonSelection);
      setDraft(readyDraft);
      setFlowState("preview_loading");
      const nextPreview = await previewBroadcast(readyDraft.id);
      setDraft(nextPreview);
      setPreview(nextPreview);
      setFlowState("preview_ready");
    } catch (err) {
      setFlowState("failed");
      setError(broadcastErrorMessage(err, "broadcast.error_preview"));
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const handleSend = async () => {
    if (!draft || submittingRef.current) return;
    try {
      submittingRef.current = true;
      setSubmitting(true);
      setFlowState("sending");
      setError(null);
      await sendBroadcast(draft.id);
      setSuccess(t("broadcast.sent", locale));
      setFlowState("sent");
      setDraft(null);
      setPreview(null);
      setText("");
      setAttachment(null);
      setButtonSelection("none");
      await loadHistory();
    } catch (err) {
      setFlowState("failed");
      setError(broadcastErrorMessage(err, "broadcast.error_send"));
    } finally {
      submittingRef.current = false;
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
    setAttachment(null);
    setButtonSelection("none");
    setError(null);
    setFlowState("cancelled");
    setSuccess(t("broadcast.cancelled", locale));
  };

  const handleBackToEdit = () => {
    setPreview(null);
    setError(null);
    setFlowState("composer");
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

      <div style={{ border: "1px solid hsl(var(--border-hsl))", background: "rgba(255,255,255,0.03)", color: "hsl(var(--text-hint-hsl))", borderRadius: "8px", padding: "10px 12px", fontSize: "12px", fontWeight: 700 }}>
        {t(`broadcast.state_${flowState}`, locale)}
      </div>

      <section style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Radio size={16} style={{ color: "hsl(var(--accent-hsl))" }} />
          <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "#fff" }}>{t("broadcast.create", locale)}</h3>
        </div>
        <textarea
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setPreview(null);
            setSuccess(null);
            setFlowState("composer");
          }}
          disabled={submitting}
          placeholder={t("broadcast.text_placeholder", locale)}
          style={{ minHeight: "132px", resize: "vertical", borderRadius: "8px", border: "1px solid hsl(var(--border-hsl))", background: "hsl(var(--card-bg-hsl))", color: "#fff", padding: "12px", fontSize: "14px", lineHeight: 1.5, outline: "none" }}
        />
        <label
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "10px",
            border: "1px dashed hsl(var(--border-hsl))",
            background: "rgba(255,255,255,0.03)",
            borderRadius: "8px",
            padding: "10px 12px",
            color: attachment ? "#fff" : "hsl(var(--text-hint-hsl))",
            cursor: submitting ? "not-allowed" : "pointer",
            fontSize: "12px",
            fontWeight: 700,
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
            <Paperclip size={16} />
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {attachment ? attachment.name : t("broadcast.attachment_add", locale)}
            </span>
          </span>
          {attachment && (
            <button
              type="button"
              onClick={(event) => {
                event.preventDefault();
                setAttachment(null);
                setPreview(null);
                setSuccess(null);
                setFlowState("composer");
              }}
              style={{ border: "none", background: "transparent", color: "hsl(var(--text-hint-hsl))", cursor: "pointer" }}
            >
              <X size={14} />
            </button>
          )}
          <input
            type="file"
            disabled={submitting}
            accept="image/*,video/*,.pdf,.txt,.csv,.doc,.docx,.xls,.xlsx"
            onChange={(event) => {
              setAttachment(event.target.files?.[0] || null);
              setPreview(null);
              setSuccess(null);
              setFlowState("composer");
            }}
            style={{ display: "none" }}
          />
        </label>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "8px" }}>
          {buttonOptions.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => {
                setButtonSelection(option);
                setPreview(null);
                setSuccess(null);
                setFlowState("composer");
              }}
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
            {submitting && flowState === "saving"
              ? t("broadcast.state_saving", locale)
              : submitting && flowState === "preview_loading"
                ? t("broadcast.state_preview_loading", locale)
                : t("broadcast.preview", locale)}
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
            <span>{t("broadcast.preview_buttons", locale)}</span>
            <b style={{ color: "#fff" }}>{t(`broadcast.button_${preview.button_selection || "none"}`, locale)}</b>
          </div>
          {preview.file_name && (
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "hsl(var(--text-hint-hsl))", fontSize: "12px" }}>
              <Paperclip size={14} />
              <span>{preview.file_name}</span>
            </div>
          )}
          {preview.validation_warnings?.map((warning) => (
            <div key={warning} style={{ color: "#ffd166", fontSize: "12px" }}>{warning}</div>
          ))}
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>
            <span>{t("broadcast.recipients", locale)}</span>
            <b style={{ color: "#fff" }}>{preview.eligible_recipient_count}</b>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={handleBackToEdit}
              disabled={submitting}
              style={{ flex: 1, padding: "12px", borderRadius: "8px", border: "1px solid hsl(var(--border-hsl))", background: "rgba(255,255,255,0.04)", color: "#fff", fontWeight: 700, cursor: submitting ? "not-allowed" : "pointer" }}
            >
              {t("broadcast.back_edit", locale)}
            </button>
            <button
              onClick={handleSend}
              disabled={submitting}
              style={{ flex: 1, padding: "12px", borderRadius: "8px", border: "none", background: "hsl(var(--success-hsl))", color: "#fff", fontWeight: 800, cursor: submitting ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}
            >
              <Send size={16} /> {submitting ? t("broadcast.state_sending", locale) : t("broadcast.confirm_send", locale)}
            </button>
          </div>
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
                {item.file_name && (
                  <span style={{ color: "hsl(var(--text-hint-hsl))", fontSize: "11px" }}>
                    {t("broadcast.attachment", locale)}: {item.file_name}
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
