"use client";

import { cn } from "@/lib/utils";

interface RealmBadgeProps {
  realm: string | null;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

const realmConfig = {
  assess: {
    label: "Assess",
    color: "bg-realm-assess",
    textColor: "text-white",
    icon: "🔴",
  },
  decide: {
    label: "Decide",
    color: "bg-realm-decide",
    textColor: "text-white",
    icon: "🟠",
  },
  do: {
    label: "Do",
    color: "bg-realm-do",
    textColor: "text-white",
    icon: "🟢",
  },
};

export function RealmBadge({ realm, size = "md", showLabel = true }: RealmBadgeProps) {
  if (!realm) return null;

  const config = realmConfig[realm as keyof typeof realmConfig];
  if (!config) return null;

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full font-medium",
        config.color,
        config.textColor,
        {
          "px-2 py-0.5 text-xs": size === "sm",
          "px-3 py-1 text-sm": size === "md",
          "px-4 py-1.5 text-base": size === "lg",
        }
      )}
    >
      <span className="mr-1">{config.icon}</span>
      {showLabel && <span>{config.label}</span>}
    </span>
  );
}
