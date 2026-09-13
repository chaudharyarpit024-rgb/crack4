import { useState, useEffect } from "react";
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
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, spacing, radius } from "@/src/theme";
import { api, setToken } from "@/src/api";
import {
  startVerificationCooldown,
  getVerificationCooldownSync,
} from "@/src/utils/verificationCooldown";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendMsg, setResendMsg] = useState("");
  const [needsVerification, setNeedsVerification] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const interval = setInterval(() => {
      const remaining = getVerificationCooldownSync(email);
      setCooldown(remaining);
      if (remaining <= 0) {
        clearInterval(interval);
      }
    }, 500);
    return () => clearInterval(interval);
  }, [cooldown, email]);

  const submit = async () => {
    if (!email || !password) {
      setErr("Enter email and password");
      return;
    }
    setLoading(true);
    setErr("");
    setResendMsg("");
    setNeedsVerification(false);
    try {
      const res = await api<{ token: string; user: any }>("/auth/login", {
        method: "POST",
        body: { email, password },
        auth: false,
      });
      await setToken(res.token);
      const u = res.user;
      if (!u.goal || !u.weight_kg || !u.height_cm) router.replace("/onboarding");
      else router.replace("/(tabs)");
    } catch (e: any) {
      if (e.status === 403) {
        setErr("Email not verified. Check your inbox for the verification link.");
        setNeedsVerification(true);
        const remaining = getVerificationCooldownSync(email);
        if (remaining > 0) {
          setCooldown(remaining);
        }
      } else {
        setErr(e.message || "Login failed");
        setNeedsVerification(false);
      }
    } finally {
      setLoading(false);
    }
  };

  const resendVerification = async () => {
    if (!email || cooldown > 0 || resending) return;
    setResending(true);
    setResendMsg("");
    try {
      const res = await api<{ ok: boolean; message: string; cooldown?: boolean; retry_after?: number }>(
        "/auth/resend-verification",
        {
          method: "POST",
          body: { email },
          auth: false,
        }
      );
      const retrySec = res.retry_after && res.retry_after > 0 ? res.retry_after : 60;
      await startVerificationCooldown(email, retrySec);
      setCooldown(retrySec);
      if (res.cooldown && res.retry_after) {
        setResendMsg(res.message || `Please wait ${res.retry_after}s before requesting a new link.`);
      } else {
        setResendMsg("Verification email sent! Please check your inbox and spam folder.");
      }
    } catch (e: any) {
      setResendMsg(e.message || "Could not resend. Try again in a moment.");
    } finally {
      setResending(false);
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

          <Text style={styles.h1}>Welcome back</Text>
          <Text style={styles.sub}>Log in to continue tracking</Text>

          <Text style={styles.label}>Email</Text>
          <TextInput
            testID="login-email-input"
            style={styles.input}
            placeholder="you@example.com"
            placeholderTextColor={colors.muted}
            autoCapitalize="none"
            keyboardType="email-address"
            value={email}
            onChangeText={setEmail}
          />
          <Text style={styles.label}>Password</Text>
          <TextInput
            testID="login-password-input"
            style={styles.input}
            placeholder="••••••••"
            placeholderTextColor={colors.muted}
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />

          <Pressable
            testID="login-forgot-password-link"
            onPress={() => router.push({ pathname: "/forgot-password" as any, params: { email } })}
            style={styles.forgotWrap}
          >
            <Text style={styles.forgotTxt}>Forgot password?</Text>
          </Pressable>

          {err ? (
            <Text style={styles.err} testID="login-error">
              {err}
            </Text>
          ) : null}

          {needsVerification ? (
            <Pressable
              testID="login-resend-verification-button"
              onPress={resendVerification}
              disabled={resending || cooldown > 0}
              style={({ pressed }) => [
                styles.btnSecondary,
                cooldown > 0 && styles.btnSecondaryCooldown,
                (pressed || resending) && cooldown <= 0 && { opacity: 0.7 },
              ]}
            >
              {resending ? (
                <ActivityIndicator color={cooldown > 0 ? colors.muted : colors.brand} />
              ) : (
                <Text style={[styles.btnSecondaryTxt, cooldown > 0 && styles.btnSecondaryCooldownTxt]}>
                  {cooldown > 0 ? `Send again in ${cooldown}s` : "Resend verification email"}
                </Text>
              )}
            </Pressable>
          ) : null}

          {resendMsg ? (
            <Text style={styles.info} testID="login-resend-msg">
              {resendMsg}
            </Text>
          ) : null}

          <Pressable
            testID="login-submit-button"
            onPress={submit}
            disabled={loading}
            style={({ pressed }) => [
              styles.btn,
              (pressed || loading) && { opacity: 0.85 },
            ]}
          >
            {loading ? (
              <ActivityIndicator color={colors.onBrand} />
            ) : (
              <Text style={styles.btnTxt}>Log in</Text>
            )}
          </Pressable>

          <Pressable
            testID="go-signup-link"
            onPress={() => router.push("/signup")}
            style={{ marginTop: spacing.lg }}
          >
            <Text style={styles.link}>
              New here? <Text style={{ color: colors.brand, fontWeight: "700" }}>Create account</Text>
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
  brand: {
    fontSize: 32,
    fontWeight: "900",
    color: colors.brand,
    letterSpacing: 3,
  },
  tag: { fontSize: 11, color: colors.muted, letterSpacing: 2, marginBottom: spacing.xxl },
  h1: { fontSize: 26, fontWeight: "800", color: colors.onSurface },
  sub: { fontSize: 14, color: colors.muted, marginTop: spacing.xs, marginBottom: spacing.xl },
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
  btnSecondary: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: colors.brand,
    paddingVertical: 14,
    borderRadius: radius.md,
    alignItems: "center",
    marginTop: spacing.md,
  },
  btnSecondaryTxt: { color: colors.brand, fontSize: 15, fontWeight: "700" },
  btnSecondaryCooldown: {
    borderColor: colors.border,
    backgroundColor: colors.surface2,
  },
  btnSecondaryCooldownTxt: {
    color: colors.muted,
    fontWeight: "600",
  },
  forgotWrap: { alignSelf: "flex-end", marginTop: spacing.sm, paddingVertical: 4 },
  forgotTxt: { color: colors.brand, fontSize: 13, fontWeight: "600" },
  err: { color: colors.error, marginTop: spacing.md, fontSize: 13 },
  info: { color: colors.brand, marginTop: spacing.md, fontSize: 13 },
  link: { textAlign: "center", color: colors.muted, fontSize: 14 },
});
