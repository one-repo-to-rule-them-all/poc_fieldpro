import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import Cookies from "js-cookie";
import { authApi, setAccessToken } from "@/lib/api";
import type { User, Tenant } from "@/types";

interface AuthState {
  user: User | null;
  tenant: Tenant | null;
  accessToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  setTokens: (access: string, refresh: string) => void;
  refreshToken: () => Promise<boolean>;
  updateUser: (user: Partial<User>) => void;
  setUser: (user: User, tenant: Tenant) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      tenant: null,
      accessToken: null, // NOT persisted — security best practice
      isLoading: false,
      isAuthenticated: false,

      setTokens: (access: string, refresh: string) => {
        // Keep access token in memory only
        setAccessToken(access);
        set({ accessToken: access, isAuthenticated: true });

        // Refresh token in a cookie (should be httpOnly in production, but
        // we set it here for SPA compatibility; backend should also set it)
        Cookies.set("refresh_token", refresh, {
          expires: 30,
          sameSite: "strict",
          secure: process.env.NODE_ENV === "production",
        });
      },

      setUser: (user: User, tenant: Tenant) => {
        set({ user, tenant, isAuthenticated: true });
      },

      login: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const response = await authApi.login(email, password);
          get().setTokens(response.access_token, response.refresh_token);
          set({
            user: response.user,
            tenant: response.tenant,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        set({ isLoading: true });
        try {
          await authApi.logout();
        } catch {
          // Ignore logout errors — always clear local state
        } finally {
          setAccessToken(null);
          Cookies.remove("refresh_token");
          set({
            user: null,
            tenant: null,
            accessToken: null,
            isLoading: false,
            isAuthenticated: false,
          });
        }
      },

      refreshToken: async (): Promise<boolean> => {
        // The backend's refresh endpoint accepts the refresh_token from either
        // the JSON body or the HttpOnly cookie set at login. js-cookie can't
        // read HttpOnly cookies, so we pass whatever it gives us (empty string
        // for web/HttpOnly) and let withCredentials attach the cookie.
        const refreshToken = Cookies.get("refresh_token") ?? "";

        try {
          const response = await authApi.refreshToken(refreshToken);
          setAccessToken(response.access_token);
          set({ accessToken: response.access_token, isAuthenticated: true });
          return true;
        } catch {
          setAccessToken(null);
          Cookies.remove("refresh_token");
          set({
            user: null,
            tenant: null,
            accessToken: null,
            isAuthenticated: false,
          });
          return false;
        }
      },

      updateUser: (partial: Partial<User>) => {
        const current = get().user;
        if (current) {
          set({ user: { ...current, ...partial } });
        }
      },

      clearAuth: () => {
        setAccessToken(null);
        Cookies.remove("refresh_token");
        set({
          user: null,
          tenant: null,
          accessToken: null,
          isAuthenticated: false,
        });
      },
    }),
    {
      name: "fieldpro-auth",
      storage: createJSONStorage(() =>
        typeof window !== "undefined" ? localStorage : ({} as Storage)
      ),
      // Only persist user and tenant — never the access token
      partialize: (state) => ({
        user: state.user,
        tenant: state.tenant,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        if (state && state.isAuthenticated) {
          // On rehydration, access token is gone (memory-only).
          // The refresh flow will restore it on the first API call.
          state.accessToken = null;
        }
      },
    }
  )
);
