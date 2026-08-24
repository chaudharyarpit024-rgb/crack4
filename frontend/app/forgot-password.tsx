import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  ScrollView,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";

export default function ForgotPassword() {
  const router = useRouter();
  const params = useLocalSearchParams<{ email?: string | string[] }>();
  const initialEmail = Array.isArray(params.email) ? params.email[0] : params.email || "";
  const [email, setEmail] = useState(initialEmail);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const interval = setInterval(() => {
      setCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [cooldown]);

  const submit = async () => {
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) {
      setErr("Please enter your email address");
      return;
    }
    if (cooldown > 0) return;

    setLoading(true);
    setErr("");
    setMsg("");
    try {
      const res = await api<{ ok: boolean; message: string; cooldown?: boolean; retry_after?: number }>(
        "/auth/forgot-password",
        {
          method: "POST",
          body: { email: trimmed },
          auth: false,
        }
      );
      if (res.cooldown && res.retry_after) {
        setCooldown(res.retry_after);
        setMsg(res.message || `Please wait ${res.retry_after}s before requesting a new link.`);
      } else {
        setCooldown(60);
        setMsg("If an account exists with that email, a password reset link has been sent. Check your inbox and spam folder.");
      }
    } catch (e: any) {
      setErr(e.message || "Failed to send reset link. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.wrap}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <Text style={styles.brand}>CRACK</Text>
          <Text style={styles.tag}>Track It First</Text>

          <Text style={styles.h1}>Forgot Password</Text>
          <Text style={styles.sub}>
            Enter your email and we'll send you a link to reset your password.
          </Text>

          <Text style={styles.label}>Email</Text>
          <TextInput
            testID="forgot-password-email-input"
            style={styles.input}
            placeholder="you@example.com"
            placeholderTextColor={colors.muted}
            autoCapitalize="none"
            keyboardType="email-address"
            value={email}
            onChangeText={(t) => {
              setEmail(t);
              setErr("");
            }}
          />

          {err ? (
            <Text style={styles.err} testID="forgot-password-error">
              {err}
            </Text>
          ) : null}

          {msg ? (
            <Text style={styles.info} testID="forgot-password-msg">
              {msg}
            </Text>
          ) : null}

          <Pressable
            testID="forgot-password-submit-button"
            onPress={submit}
            disabled={loading || cooldown > 0}
            style={({ pressed }) => [
              styles.btn,
              (pressed || loading || cooldown > 0) && { opacity: 0.75 },
            ]}
          >
            {loading ? (
              <ActivityIndicator color={colors.onBrand} />
            ) : (
              <Text style={styles.btnTxt}>
                {cooldown > 0 ? `Resend link in ${cooldown}s` : "Send reset link"}
              </Text>
            )}
          </Pressable>

          <Pressable
            testID="forgot-password-back-to-login"
            onPress={() => router.replace("/login")}
            style={{ marginTop: spacing.xl }}
          >
            <Text style={styles.link}>
              Remembered your password?{" "}
              <Text style={{ color: colors.brand, fontWeight: "700" }}>Log in</Text>
            </Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.surface },
  scroll: { padding: spacing.xl, paddingTop: spacing.xxl, paddingBottom: spacing.xxxl },
  brand: { fontSize: 32, fontWeight: "900", color: colors.brand, letterSpacing: 3 },
  tag: { fontSize: 11, color: colors.muted, letterSpacing: 2, marginBottom: spacing.xxl },
  h1: { fontSize: 26, fontWeight: "800", color: colors.onSurface },
  sub: { fontSize: 14, color: colors.muted, marginTop: spacing.xs, marginBottom: spacing.xl, lineHeight: 20 },
  label: { fontSize: 13, color: colors.onSurface2, marginTop: spacing.md, marginBottom: spacing.xs, fontWeight: "600" },
  input: {
    backgroundColor: colors.surface2,
    paddingHorizontal: spacing.lg,
    paddingVertical: 14,
    borderRadius: radius.md,
    fontSize: 16,
    color: colors.onSurface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  btn: {
    backgroundColor: colors.brand,
    paddingVertical: 16,
    borderRadius: radius.md,
    alignItems: "center",
    marginTop: spacing.xl,
  },
  btnTxt: { color: colors.onBrand, fontSize: 16, fontWeight: "700" },
  err: { color: colors.error, marginTop: spacing.md, fontSize: 13 },
  info: { color: colors.brand, marginTop: spacing.md, fontSize: 13, lineHeight: 18 },
  link: { textAlign: "center", color: colors.muted, fontSize: 14 },
});
