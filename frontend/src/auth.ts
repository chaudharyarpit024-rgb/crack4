import { useEffect, useState } from "react";
import { api, clearToken } from "./api";

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

  const refresh = async () => {
    try {
      const u = await api<User>("/auth/me");
      setUser(u);
    } catch {
      setUser(null);
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

  return { user, loading, refresh, logout, setUser };
}
