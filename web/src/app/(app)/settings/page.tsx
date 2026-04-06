"use client";

import { useAuthStore } from "@/stores/auth-store";
import { useTheme } from "@/components/theme-provider";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
  const { user, updateTheme, logout } = useAuthStore();
  const { theme, setTheme } = useTheme();

  const handleThemeChange = (newTheme: "light" | "dark" | "system") => {
    setTheme(newTheme);
    updateTheme(newTheme);
  };

  return (
    <div className="flex-1 flex flex-col">
      <Header title="Settings" />

      <div className="p-6 max-w-2xl">
        {/* Profile */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-4">Profile</h2>
          <div className="p-4 bg-muted rounded-lg">
            <div className="flex items-center gap-4">
              {user?.picture_url ? (
                <img
                  src={user.picture_url}
                  alt={user.name || user.email}
                  className="h-16 w-16 rounded-full"
                />
              ) : (
                <div className="h-16 w-16 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xl font-medium">
                  {(user?.name || user?.email || "?")[0].toUpperCase()}
                </div>
              )}
              <div>
                <p className="font-medium">{user?.name || "No name"}</p>
                <p className="text-sm text-muted-foreground">{user?.email}</p>
              </div>
            </div>
          </div>
        </section>

        {/* Theme */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-4">Theme</h2>
          <div className="flex gap-2">
            {(["light", "dark", "system"] as const).map((t) => (
              <button
                key={t}
                onClick={() => handleThemeChange(t)}
                className={`px-4 py-2 rounded-lg text-sm font-medium ${
                  theme === t
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-muted/80"
                }`}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </section>

        {/* About */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-4">About</h2>
          <div className="p-4 bg-muted rounded-lg space-y-2 text-sm">
            <p>
              <strong>AIGernon</strong> - Your cognitive companion
            </p>
            <p className="text-muted-foreground">
              Built on the Assess-Decide-Do framework for thoughtful, intentional thinking.
            </p>
          </div>
        </section>

        {/* Danger Zone */}
        <section>
          <h2 className="text-lg font-semibold mb-4 text-red-600">Danger Zone</h2>
          <div className="p-4 border border-red-200 rounded-lg dark:border-red-900">
            <p className="text-sm text-muted-foreground mb-4">
              Sign out of your account. You can sign back in at any time.
            </p>
            <Button variant="destructive" onClick={logout}>
              Sign Out
            </Button>
          </div>
        </section>
      </div>
    </div>
  );
}
