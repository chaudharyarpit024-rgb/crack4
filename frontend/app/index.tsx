import { useEffect } from "react";
import { View, Text, StyleSheet, ActivityIndicator } from "react-native";
import { useRouter } from "expo-router";
import { api } from "@/src/api";
import { colors, spacing } from "@/src/theme";
import { isNetworkError, isAuthError, isConnected } from "@/src/utils/network";

export default function Index() {
  const router = useRouter();

  useEffect(() => {
    (async () => {
      // ── 1. Quick connectivity pre-check ──────────────────────
      // If the device knows it's offline, skip the API call entirely
      // and go straight to the network error screen.
      const online = await isConnected();
      if (!online) {
        router.replace("/network-error");
        return;
      }

      // ── 2. Try the auth check ────────────────────────────────
      try {
        const me = await api<any>("/auth/me");
        if (!me.goal || !me.weight_kg || !me.height_cm) {
          router.replace("/onboarding");
        } else {
          router.replace("/(tabs)");
        }
      } catch (err: any) {
        // ── 3. Classify the error ──────────────────────────────
        if (isNetworkError(err)) {
          // Network issue — do NOT go to login. User is still logged in.
          router.replace("/network-error");
        } else if (isAuthError(err)) {
          // 401 — token is genuinely expired or invalid.
          // Check if user has a stored token → session expired page.
          // No token → regular login page (first-time user).
          router.replace("/session-expired");
        } else if (err?.status === 503) {
          // Server under maintenance
          router.replace("/maintenance");
        } else if (err?.status && err.status >= 500) {
          // Other server errors (500, 502, etc.)
          router.replace("/server-error");
        } else {
          // Unknown error — most likely no token stored, fresh install.
          // Default to login.
          router.replace("/login");
        }
      }
    })();
  }, []);

  return (
    <View style={styles.wrap} testID="splash-screen">
      <Text style={styles.brand}>CRACK</Text>
      <Text style={styles.tag}>Track It First</Text>
      <ActivityIndicator color={colors.brand} style={{ marginTop: spacing.xl }} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  brand: {
    fontSize: 48,
    fontWeight: "900",
    color: colors.brand,
    letterSpacing: 4,
  },
  tag: {
    marginTop: spacing.sm,
    fontSize: 14,
    color: colors.muted,
    letterSpacing: 2,
    textTransform: "uppercase",
  },
});
