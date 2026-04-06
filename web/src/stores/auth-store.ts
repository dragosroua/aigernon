import { create } from "zustand";
import { authApi, User } from "@/lib/api";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  checkAuth: (token?: string) => Promise<void>;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  updateTheme: (theme: string) => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isLoading: true,
  error: null,

  checkAuth: async (token?: string) => {
    try {
      set({ isLoading: true, error: null });
      const user = await authApi.getMe(token);
      set({ user, isLoading: false });
    } catch (error) {
      console.error("checkAuth failed:", error);
      set({ user: null, isLoading: false, error: error instanceof Error ? error.message : "Auth check failed" });
    }
  },

  login: async () => {
    try {
      const { redirect_url } = await authApi.getLoginUrl();
      window.location.href = redirect_url;
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Login failed" });
    }
  },

  logout: async () => {
    try {
      await authApi.logout();
      set({ user: null });
      window.location.href = "/login";
    } catch (error) {
      set({ error: error instanceof Error ? error.message : "Logout failed" });
    }
  },

  updateTheme: async (theme: string) => {
    try {
      await authApi.updateTheme(theme);
      const { user } = get();
      if (user) {
        set({ user: { ...user, theme } });
      }
    } catch (error) {
      console.error("Failed to update theme:", error);
    }
  },
}));
