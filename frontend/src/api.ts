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
  // EXPO_PUBLIC_BACKEND_URL must be set in .env – no hardcoded fallback
  if (!envUrl) {
    throw new Error(
      "EXPO_PUBLIC_BACKEND_URL is not set. " +
      "Copy frontend/.env.example to frontend/.env and fill in the URL."
    );
  }
  return envUrl;
}

const TOKEN_KEY = "crack.auth.token";

// Web: store token in memory only (never in localStorage/sessionStorage).
// In-memory storage is not accessible to XSS or browser extensions.
// Trade-off: token is lost on hard page refresh — user must re-authenticate.
// For persistence without XSS risk, migrate to HttpOnly cookies set server-side.
let _webToken: string | null = null;

export async function getToken(): Promise<string | null> {
  if (Platform.OS === "web") {
    return _webToken;
  }
  return await SecureStore.getItemAsync(TOKEN_KEY);
}

export async function setToken(token: string) {
  if (Platform.OS === "web") {
    _webToken = token;
    return;
  }
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function clearToken() {
  if (Platform.OS === "web") {
    _webToken = null;
    return;
  }
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: any; auth?: boolean; timeoutMs?: number } = {}
): Promise<T> {
  const { method = "GET", body, auth = true, timeoutMs = 15000 } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const t = await getToken();
    if (t) headers.Authorization = `Bearer ${t}`;
  }
  const baseUrl = getBaseUrl();

  // AbortController timeout — prevents indefinite hangs on slow networks
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(`${baseUrl}/api${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (fetchErr: any) {
    clearTimeout(timer);
    // fetch() only throws on *network-level* failures (no response at all)
    // or AbortController timeouts. Re-throw WITHOUT a .status so callers
    // can distinguish from HTTP errors.
    if (fetchErr?.name === "AbortError") {
      const err = new Error("Network request timed out") as Error & { isTimeout: boolean };
      err.isTimeout = true;
      throw err;
    }
    throw new Error(fetchErr?.message || "Network request failed");
  } finally {
    clearTimeout(timer);
  }

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
