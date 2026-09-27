/**
 * Network-aware error classification utilities.
 *
 * Used to distinguish network/timeout failures from actual
 * authentication errors so the app never wrongly bounces
 * a logged-in user to the login screen.
 */

import NetInfo, { NetInfoState } from "@react-native-community/netinfo";

/* ------------------------------------------------------------------ */
/*  Error classification                                               */
/* ------------------------------------------------------------------ */

/** Errors that indicate a network problem, NOT an auth problem. */
export function isNetworkError(err: unknown): boolean {
  if (!err) return false;

  // If it has an HTTP status code, it reached the server — not a network error.
  if (typeof (err as any).status === "number") return false;

  const msg =
    typeof err === "string"
      ? err
      : (err as Error).message ?? String(err);

  const patterns = [
    "network request failed",
    "failed to fetch",
    "networkerror",
    "network error",
    "timeout",
    "abort",
    "econnrefused",
    "econnreset",
    "enotfound",
    "dns",
    "socket",
    "ssl",
    "tls",
    "unable to resolve host",
    "could not connect",
    "no internet",
    "the internet connection appears to be offline",
  ];

  const lower = msg.toLowerCase();
  return patterns.some((p) => lower.includes(p));
}

/** Is the error an HTTP 401 Unauthorized? */
export function isAuthError(err: unknown): boolean {
  return (err as any)?.status === 401;
}

/* ------------------------------------------------------------------ */
/*  Connectivity check                                                 */
/* ------------------------------------------------------------------ */

/** Returns `true` when the device thinks it's connected. */
export async function isConnected(): Promise<boolean> {
  try {
    const state: NetInfoState = await NetInfo.fetch();
    return state.isConnected === true && state.isInternetReachable !== false;
  } catch {
    // NetInfo can fail in some Expo Go environments — assume connected.
    return true;
  }
}

/* ------------------------------------------------------------------ */
/*  Connectivity listener hook helpers                                 */
/* ------------------------------------------------------------------ */

/**
 * Subscribe to network state changes.
 * Returns an unsubscribe function.
 */
export function onConnectivityChange(
  callback: (connected: boolean) => void
): () => void {
  return NetInfo.addEventListener((state) => {
    callback(state.isConnected === true && state.isInternetReachable !== false);
  });
}
