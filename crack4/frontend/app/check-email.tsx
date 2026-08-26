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
import { api } from "@/src/api";

export default function CheckEmail() {
  const router = useRouter();
  const params = useLocalSearchParams<{ email?: string | string[] }>();
  const email = Array.isArray(params.email) ? params.email[0] : params.email;
  const [resending, setResending] = useState(false);
  const [msg, setMsg] = useState("");
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const interval = setInterval(() => {
      setCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [cooldown]);

  const resend = async () => {
    if (!email || cooldown > 0) return;
    setResending(true);
    setMsg("");
    try {
      const res = await api<{ ok: boolean; message: string; cooldown?: boolean; retry_after?: number }>(
        "/auth/resend-verification",
        {
          method: "POST",
          body: { email },
          auth: false,
        }
      );
      if (res.cooldown && res.retry_after) {
        setCooldown(res.retry_after);
        setMsg(res.message || `Please wait ${res.retry_after}s before requesting a new link.`);
      } else {
        setCooldown(60);
        setMsg("Verification email sent! Please check your inbox and spam folder.");
      }
    } catch (e: any) {
      setMsg(e.message || "Could not resend. Try again in a moment.");
    } finally {
      setResending(false);
    }
  };

  return (
    <SafeAreaView style={styles.wrap}>
      <View style={styles.body}>
        <Text style={styles.brand}>CRACK</Text>
        <Text style={styles.tag}>Track It First</Text>

        <Text style={styles.h1}>Check your email</Text>
        <Text style={styles.sub}>
          We sent a verification link to
        </Text>
        <Text style={styles.email} testID="check-email-address">
          {email || "your email"}
        </Text>
        <Text style={styles.help}>
          Tap the link in the email to activate your account. The link expires in 24 hours.
        </Text>

        {msg ? (
          <Text style={styles.info} testID="check-email-resend-msg">
            {msg}
          </Text>
        ) : null}

        <Pressable
          testID="check-email-resend-button"
          onPress={resend}
          disabled={resending || !email || cooldown > 0}
          style={({ pressed }) => [
            styles.btn,
            (pressed || resending || cooldown > 0 || !email) && { opacity: 0.7 },
          ]}
        >
          {resending ? (
            <ActivityIndicator color={colors.onBrand} />
          ) : (
            <Text style={styles.btnTxt}>
              {cooldown > 0 ? `Resend email in ${cooldown}s` : "Resend verification email"}
            </Text>
          )}
        </Pressable>

        <Pressable
          testID="check-email-back-to-login"
          onPress={() => router.replace("/login")}
          style={{ marginTop: spacing.lg }}
        >
          <Text style={styles.link}>
            Wrong email? <Text style={{ color: colors.brand, fontWeight: "700" }}>Back to login</Text>
          </Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.surface },
  body: { flex: 1, padding: spacing.xl, paddingTop: spacing.xxl },
  brand: { fontSize: 32, fontWeight: "900", color: colors.brand, letterSpacing: 3 },
  tag: { fontSize: 11, color: colors.muted, letterSpacing: 2, marginBottom: spacing.xxl },
  h1: { fontSize: 26, fontWeight: "800", color: colors.onSurface },
  sub: { fontSize: 14, color: colors.muted, marginTop: spacing.xs },
  email: {
    fontSize: 16,
    color: colors.onSurface,
    fontWeight: "700",
    marginTop: spacing.xs,
  },
  help: {
    fontSize: 13,
    color: colors.muted,
    lineHeight: 20,
    marginTop: spacing.lg,
  },
  info: {
    fontSize: 13,
    color: colors.brand,
    marginTop: spacing.lg,
    lineHeight: 18,
  },
  btn: {
    backgroundColor: colors.brand,
    paddingVertical: 16,
    borderRadius: radius.md,
    alignItems: "center",
    marginTop: spacing.xl,
  },
  btnTxt: { color: colors.onBrand, fontSize: 16, fontWeight: "700" },
  link: { textAlign: "center", color: colors.muted, fontSize: 14 },
});
