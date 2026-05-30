import React from "react";
import { FolderOpen } from "lucide-react";

interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  actionLabel,
  onAction,
}) => {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "32px 16px",
        textAlign: "center",
        flex: 1,
        color: "hsl(var(--text-hint-hsl))",
      }}
    >
      <FolderOpen size={48} strokeWidth={1.5} style={{ marginBottom: "16px", color: "hsl(var(--border-hsl))" }} />
      <h3 style={{ fontSize: "16px", fontWeight: 600, color: "hsl(var(--text-primary-hsl))", marginBottom: "6px" }}>
        {title}
      </h3>
      <p style={{ fontSize: "14px", maxWidth: "280px", marginBottom: "20px" }}>
        {description}
      </p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          style={{
            padding: "8px 16px",
            backgroundColor: "hsl(var(--accent-hsl))",
            color: "hsl(var(--tg-theme-button-text-color))",
            borderRadius: "var(--radius-sm)",
            fontSize: "14px",
            fontWeight: 600,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "hsl(var(--accent-hover-hsl))")}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "hsl(var(--accent-hsl))")}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};
