import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

export function getBaseUrl(): string {
  const envUrl = process.env.EXPO_PUBLIC_BACKEND_URL;
  if (Platform.OS !== "web") {
    // If on a physical phone or emulator and URL is localhost, resolve laptop's LAN IP
    if (!envUrl || envUrl.includes("localhost") || envUrl.includes("127.0.0.1")) {
      const hostUri = Constants.expoConfig?.hostUri || (Constants as any).manifest2?.extra?.expoGo?.debuggerHost;
      if (hostUri) {
        const ip = hostUri.split(":")[0];
        return `http://${ip}:8000`;
      }
    }
  }
  return envUrl || "https://crack4-avoa.onrender.com";
}

const TOKEN_KEY = "crack.auth.token";

async function getToken(): Promise<string | null> {
  if (Platform.OS === "web") {
    try {
      return typeof localStorage !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
    } catch {
      return null;
    }
  }
  return await SecureStore.getItemAsync(TOKEN_KEY);
}

export async function setToken(token: string) {
  if (Platform.OS === "web") {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {}
    return;
  }
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function clearToken() {
  if (Platform.OS === "web") {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {}
    return;
  }
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: any; auth?: boolean } = {}
): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const t = await getToken();
    if (t) headers.Authorization = `Bearer ${t}`;
  }
  const baseUrl = getBaseUrl();
  const res = await fetch(`${baseUrl}/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const txt = await res.text();
  let data: any = null;
  try {
    data = txt ? JSON.parse(txt) : null;
  } catch {
    data = txt;
  }
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    const err = new Error(typeof msg === "string" ? msg : JSON.stringify(msg)) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return data as T;
}

export const API_BASE = getBaseUrl();
