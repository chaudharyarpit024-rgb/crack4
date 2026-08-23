import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, spacing, radius } from "@/src/theme";
import { api, setToken } from "@/src/api";

export default function VerifyEmail() {
  const router = useRouter();
  const { token } = useLocalSearchParams<{ token?: string }>();
  const [status, setStatus] = useState<"pending" | "success" | "error">("pending");
  const [msg, setMsg] = useState("Verifying your email…");

  useEffect(() => {
    const verify = async () => {
      if (!token) {
        setStatus("error");
        setMsg("Invalid verification link. Please request a new one.");
        return;
      }
      try {
        const res = await api<{ token: string; user: any }>("/auth/verify", {
          method: "POST",
          body: { token },
          auth: false,
        });
        await setToken(res.token);
        setStatus("success");
        const u = res.user;
        if (!u.goal || !u.weight_kg || !u.height_cm) {
          router.replace("/onboarding");
        } else {
          router.replace("/(tabs)");
        }
      } catch (e: any) {
        setStatus("error");
        setMsg(e.message || "Verification failed. The link may have expired.");
      }
    };
    verify();
  }, [token, router]);

  return (
    <SafeAreaView style={styles.wrap}>
      <View style={styles.body}>
        <Text style={styles.brand}>CRACK</Text>
        <Text style={styles.tag}>Track It First</Text>

        {status === "pending" ? (
          <>
            <ActivityIndicator color={colors.brand} size="large" style={{ marginTop: spacing.xxl }} />
            <Text style={styles.h1}>Verifying…</Text>
            <Text style={styles.sub}>{msg}</Text>
          </>
        ) : status === "success" ? (
          <>
            <Text style={styles.h1}>Email verified</Text>
            <Text style={styles.sub}>Redirecting you now…</Text>
          </>
        ) : (
          <>
            <Text style={styles.h1}>Verification failed</Text>
            <Text style={styles.sub} testID="verify-email-error">
              {msg}
            </Text>
            <Pressable
              testID="verify-email-back-to-login"
              onPress={() => router.replace("/login")}
              style={({ pressed }) => [styles.btn, pressed && { opacity: 0.85 }]}
            >
              <Text style={styles.btnTxt}>Back to login</Text>
            </Pressable>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.surface },
  body: { flex: 1, padding: spacing.xl, paddingTop: spacing.xxl },
  brand: { fontSize: 32, fontWeight: "900", color: colors.brand, letterSpacing: 3 },
  tag: { fontSize: 11, color: colors.muted, letterSpacing: 2, marginBottom: spacing.xxl },
  h1: { fontSize: 24, fontWeight: "800", color: colors.onSurface, marginTop: spacing.lg },
  sub: { fontSize: 14, color: colors.muted, marginTop: spacing.xs, lineHeight: 20 },
  btn: {
    backgroundColor: colors.brand,
    paddingVertical: 16,
    borderRadius: radius.md,
    alignItems: "center",
    marginTop: spacing.xl,
  },
  btnTxt: { color: colors.onBrand, fontSize: 16, fontWeight: "700" },
});
