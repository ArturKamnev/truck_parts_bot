import React from "react";
import { LogOut } from "lucide-react";
import { type UserProfile } from "../api/auth";
import { RoleBadge } from "./RoleBadge";
import { getInitials } from "../utils/normalization";
import { t } from "../i18n";

interface TopBarProps {
  profile: UserProfile;
  isMockActive: boolean;
  onLogout: () => void;
  locale: string;
}

export const TopBar: React.FC<TopBarProps> = ({ profile, isMockActive, onLogout, locale }) => {
  const displayName = profile.display_name;
  const initial = getInitials(displayName);


  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "12px 16px",
        backgroundColor: "hsl(var(--card-bg-hsl))",
        borderBottom: "1px solid hsl(var(--border-hsl))",
        paddingTop: "calc(12px + var(--sat))", // Safe area support
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <div
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "50%",
            backgroundColor: "hsl(var(--accent-light-hsl))",
            color: "hsl(var(--accent-hsl))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: "bold",
            fontSize: "14px",
          }}
        >
          {initial}
        </div>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "14px", fontWeight: 600 }}>{displayName}</span>
            <RoleBadge role={profile.role} />
          </div>
          {profile.username && (
            <span style={{ fontSize: "12px", color: "hsl(var(--text-hint-hsl))" }}>
              @{profile.username}
            </span>
          )}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        {isMockActive && (
          <div
            style={{
              padding: "4px 8px",
              backgroundColor: "hsl(var(--danger-hsl))",
              color: "#fff",
              borderRadius: "4px",
              fontSize: "10px",
              fontWeight: 700,
              letterSpacing: "0.05em",
              boxShadow: "0 2px 4px rgba(0,0,0,0.15)",
              animation: "pulse-slow 2s infinite",
            }}
          >
            {t("profile.dev_mock_auth", locale)}
          </div>
        )}
        <button
          onClick={onLogout}
          style={{
            padding: "8px",
            borderRadius: "var(--radius-sm)",
            color: "hsl(var(--text-hint-hsl))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          title={t("common.logout", locale)}
          onMouseEnter={(e) => (e.currentTarget.style.color = "hsl(var(--danger-hsl))")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "hsl(var(--text-hint-hsl))")}
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
};
