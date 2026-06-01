import React from "react";
import { type LucideIcon } from "lucide-react";
import { type MetricPoint, type TrendPoint } from "../api/tickets";

const clampPercent = (value: number) => Math.max(0, Math.min(100, value));

const formatCompactNumber = (value: number) => {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return String(value);
};

export const EmptyMiniChart: React.FC<{ label: string }> = ({ label }) => (
  <div
    style={{
      height: "54px",
      borderRadius: "8px",
      border: "1px dashed hsl(var(--border-hsl))",
      color: "hsl(var(--text-hint-hsl))",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: "11px",
      background: "rgba(255,255,255,0.02)",
    }}
  >
    {label}
  </div>
);

export const StatCard: React.FC<{
  icon: LucideIcon;
  label: string;
  value: string | number;
  hint?: string;
  tone?: "accent" | "success" | "warning" | "danger" | "neutral";
}> = ({ icon: Icon, label, value, hint, tone = "accent" }) => {
  const color =
    tone === "success"
      ? "hsl(var(--success-hsl))"
      : tone === "warning"
        ? "hsl(var(--warning-hsl))"
        : tone === "danger"
          ? "hsl(var(--danger-hsl))"
          : tone === "neutral"
            ? "hsl(var(--text-hint-hsl))"
            : "hsl(var(--accent-hsl))";
  return (
    <div className="premium-card" style={{ padding: "13px", minHeight: "104px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px" }}>
        <span style={{ fontSize: "11px", fontWeight: 700, color: "hsl(var(--text-hint-hsl))" }}>
          {label}
        </span>
        <Icon size={15} style={{ color }} />
      </div>
      <div style={{ marginTop: "10px", fontSize: "24px", lineHeight: 1, fontWeight: 800, color: "#fff" }}>
        {value}
      </div>
      {hint && (
        <div style={{ marginTop: "8px", fontSize: "11px", color: "hsl(var(--text-hint-hsl))" }}>
          {hint}
        </div>
      )}
    </div>
  );
};

export const Sparkline: React.FC<{ points: TrendPoint[]; label: string }> = ({ points, label }) => {
  const values = points.map((point) => point.created + point.closed);
  const max = Math.max(...values, 1);
  const width = 180;
  const height = 54;
  const path = values
    .map((value, index) => {
      const x = values.length <= 1 ? 0 : (index / (values.length - 1)) * width;
      const y = height - (value / max) * (height - 8) - 4;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  if (values.every((value) => value === 0)) return <EmptyMiniChart label={label} />;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} style={{ width: "100%", height: "54px" }}>
      <path d={path} fill="none" stroke="hsl(var(--accent-hsl))" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <path d={`${path} L ${width} ${height} L 0 ${height} Z`} fill="rgba(82,136,193,0.12)" />
    </svg>
  );
};

export const DonutChart: React.FC<{ value: number; total: number; label: string }> = ({ value, total, label }) => {
  const percent = total > 0 ? clampPercent((value / total) * 100) : 0;
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const dash = (percent / 100) * circumference;

  return (
    <svg viewBox="0 0 52 52" role="img" aria-label={label} style={{ width: "58px", height: "58px" }}>
      <circle cx="26" cy="26" r={radius} fill="none" stroke="hsl(var(--border-hsl))" strokeWidth="6" />
      <circle
        cx="26"
        cy="26"
        r={radius}
        fill="none"
        stroke="hsl(var(--success-hsl))"
        strokeWidth="6"
        strokeDasharray={`${dash} ${circumference - dash}`}
        strokeLinecap="round"
        transform="rotate(-90 26 26)"
      />
      <text x="26" y="30" textAnchor="middle" fontSize="11" fontWeight="800" fill="#fff">
        {Math.round(percent)}%
      </text>
    </svg>
  );
};

export const BarList: React.FC<{ points: MetricPoint[]; emptyLabel: string }> = ({ points, emptyLabel }) => {
  const max = Math.max(...points.map((point) => point.value), 0);
  if (max === 0) return <EmptyMiniChart label={emptyLabel} />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "9px" }}>
      {points.map((point) => (
        <div key={point.label} style={{ display: "grid", gridTemplateColumns: "74px 1fr 34px", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "11px", color: "hsl(var(--text-hint-hsl))", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {point.label}
          </span>
          <div style={{ height: "7px", borderRadius: "999px", background: "rgba(255,255,255,0.05)", overflow: "hidden" }}>
            <div
              style={{
                width: `${clampPercent((point.value / max) * 100)}%`,
                height: "100%",
                borderRadius: "999px",
                background: "hsl(var(--accent-hsl))",
              }}
            />
          </div>
          <b style={{ fontSize: "11px", textAlign: "right" }}>{formatCompactNumber(point.value)}</b>
        </div>
      ))}
    </div>
  );
};
