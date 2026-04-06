"use client";

import { Bell, Sun, Moon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/components/theme-provider";
import { useNotificationStore } from "@/stores/notification-store";
import { RealmBadge } from "@/components/realm/realm-badge";
import { useChatStore } from "@/stores/chat-store";

interface HeaderProps {
  title?: string;
}

export function Header({ title = "AIGernon" }: HeaderProps) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { unreadCount } = useNotificationStore();
  const { currentRealm } = useChatStore();

  const toggleTheme = () => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  };

  return (
    <header className="flex items-center justify-between h-14 px-4 border-b border-border bg-background">
      <div className="flex items-center gap-4">
        <h1 className="font-semibold">{title}</h1>
        {currentRealm && <RealmBadge realm={currentRealm} />}
      </div>

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          {resolvedTheme === "dark" ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>

        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-red-500 text-white text-xs flex items-center justify-center">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </div>
    </header>
  );
}
