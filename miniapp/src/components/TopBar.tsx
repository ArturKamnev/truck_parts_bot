import React from "react";
import { LogOut } from "lucide-react";
import { type UserProfile } from "../api/auth";
import { RoleBadge } from "./RoleBadge";

interface TopBarProps {
  profile: UserProfile;
  isMockActive: boolean;
  onLogout: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ profile, isMockActive, onLogout }) => {
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
          {profile.display_name.charAt(0).toUpperCase()}
        </div>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "14px", fontWeight: 600 }}>{profile.display_name}</span>
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
            DEV MOCK AUTH
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
          title="Disconnect Session"
          onMouseEnter={(e) => (e.currentTarget.style.color = "hsl(var(--danger-hsl))")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "hsl(var(--text-hint-hsl))")}
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
};
