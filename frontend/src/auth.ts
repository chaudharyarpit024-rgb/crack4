import { useEffect, useState } from "react";
import { api, clearToken } from "./api";
import { isNetworkError } from "./utils/network";

export type User = {
  id: string;
  email: string;
  name?: string;
  goal?: "gain" | "lose" | "maintain" | null;
  weight_kg?: number | null;
  height_cm?: number | null;
  age?: number | null;
  gender?: string | null;
  daily_target?: number | null;
  email_verified?: boolean;
  longest_streak?: number | null;
};


export function useMe() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  /** `true` when the last fetch failed due to a network issue. */
  const [networkError, setNetworkError] = useState(false);

  const refresh = async () => {
    try {
      const u = await api<User>("/auth/me");
      setUser(u);
      setNetworkError(false);
    } catch (err) {
      if (isNetworkError(err)) {
        // Network failure — do NOT clear user state.
        // The user is still authenticated; we just can't reach the server.
        setNetworkError(true);
      } else {
        // Genuine auth failure or other error — user is not logged in.
        setUser(null);
        setNetworkError(false);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const logout = async () => {
    await clearToken();
    setUser(null);
  };

  return { user, loading, refresh, logout, setUser, networkError };
}
