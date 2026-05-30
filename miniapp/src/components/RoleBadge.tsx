import React from "react";

interface RoleBadgeProps {
  role: "customer" | "manager" | "owner" | string;
}

export const RoleBadge: React.FC<RoleBadgeProps> = ({ role }) => {
  const styles: Record<string, { bg: string; text: string; label: string }> = {
    owner: {
      bg: "rgba(224, 86, 36, 0.15)",
      text: "rgb(255, 120, 80)",
      label: "OWNER",
    },
    manager: {
      bg: "rgba(82, 136, 193, 0.15)",
      text: "rgb(112, 172, 237)",
      label: "MANAGER",
    },
    customer: {
      bg: "rgba(75, 181, 67, 0.15)",
      text: "rgb(105, 221, 97)",
      label: "CLIENT",
    },
  };

  const current = styles[role] || {
    bg: "rgba(112, 132, 153, 0.15)",
    text: "rgb(152, 172, 193)",
    label: role.toUpperCase(),
  };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 8px",
        borderRadius: "9999px",
        fontSize: "11px",
        fontWeight: 600,
        letterSpacing: "0.05em",
        backgroundColor: current.bg,
        color: current.text,
      }}
    >
      {current.label}
    </span>
  );
};
