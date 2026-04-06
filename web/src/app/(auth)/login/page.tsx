"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { systemApi } from "@/lib/api";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const router = useRouter();
  const { user, isLoading, login, checkAuth, error } = useAuthStore();
  const [oauthProvider, setOauthProvider] = useState<string>("OAuth");

  useEffect(() => {
    checkAuth();
    // Fetch the configured OAuth provider
    systemApi.config().then((config) => {
      const provider = config.oauth_provider || "OAuth";
      setOauthProvider(provider.charAt(0).toUpperCase() + provider.slice(1));
    }).catch(() => {});
  }, [checkAuth]);

  useEffect(() => {
    if (user) {
      router.push("/chat");
    }
  }, [user, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-muted">
      <div className="w-full max-w-md p-8 bg-background rounded-xl shadow-lg">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">AIGernon</h1>
          <p className="text-muted-foreground">Your cognitive companion</p>
        </div>

        <div className="space-y-4">
          {error && (
            <p className="text-sm text-red-500 text-center">{error}</p>
          )}

          <Button onClick={login} className="w-full" size="lg">
            Sign in with {oauthProvider}
          </Button>

          <p className="text-xs text-center text-muted-foreground">
            By signing in, you agree to our terms of service and privacy policy.
          </p>
        </div>
      </div>
    </div>
  );
}
