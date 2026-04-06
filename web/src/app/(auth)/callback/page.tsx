"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";

export default function CallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading, error: authError, checkAuth } = useAuthStore();
  const [localError, setLocalError] = useState<string | null>(null);
  const [authStarted, setAuthStarted] = useState(false);

  useEffect(() => {
    const token = searchParams.get("token");

    if (token && !authStarted) {
      setAuthStarted(true);

      // Store token in cookie for future requests
      document.cookie = `auth_token=${token}; path=/; max-age=${7 * 24 * 60 * 60}; samesite=lax`;

      // Check auth with token passed directly (don't rely on cookie being set yet)
      checkAuth(token);
    } else if (!token) {
      // No token, redirect to login
      router.push("/login");
    }
  }, [searchParams, checkAuth, router, authStarted]);

  // Redirect to chat once user is loaded, or show error
  useEffect(() => {
    if (authStarted && !isLoading) {
      if (user) {
        router.push("/chat");
      } else if (authError) {
        setLocalError(authError);
      }
    }
  }, [user, isLoading, authError, authStarted, router]);

  const error = localError || authError;

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4 text-red-500">Sign-in Failed</h1>
          <p className="text-muted-foreground mb-4">{error}</p>
          <button
            onClick={() => router.push("/login")}
            className="text-primary hover:underline"
          >
            Back to login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <h1 className="text-2xl font-bold mb-4">Signing in...</h1>
        <p className="text-muted-foreground">Please wait while we complete your sign-in.</p>
      </div>
    </div>
  );
}
