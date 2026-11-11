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
import { api, setToken, clearToken } from "@/src/api";
import {
  startVerificationCooldown,
  getVerificationCooldownSync,
} from "@/src/utils/verificationCooldown";

type AuthStep = "email" | "login" | "signup";

export default function Login() {
  const router = useRouter();

  // Step state: "email" (first prompt), "login" (existing account), or "signup" (new account)
  const [step, setStep] = useState<AuthStep>("email");

  // Form fields
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [userName, setUserName] = useState("");

  // Feedback & loaders
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendMsg, setResendMsg] = useState("");
  const [needsVerification, setNeedsVerification] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  // Sync verification cooldown timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const interval = setInterval(() => {
      const remaining = getVerificationCooldownSync(email.trim().toLowerCase());
      setCooldown(remaining);
      if (remaining <= 0) {
        clearInterval(interval);
      }
    }, 500);
    return () => clearInterval(interval);
  }, [cooldown, email]);

  // ── Step 1: Check Email in Database ──────────────────────────
  const handleContinueEmail = async () => {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || !cleanEmail.includes("@") || !cleanEmail.includes(".")) {
      setErr("Please enter a valid email address");
      return;
    }
    setLoading(true);
    setErr("");
    try {
      const res = await api<{ exists: boolean; email: string; email_verified?: boolean; name?: string }>(
        "/auth/check-email",
        {
          method: "POST",
          body: { email: cleanEmail },
          auth: false,
        }
      );
      if (res.exists) {
        setUserName(res.name || "");
        setStep("login");
      } else {
        setStep("signup");
      }
    } catch (e: any) {
      setErr(e.message || "Could not check email. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── Step 2A: Existing User Login ─────────────────────────────
  const handleLogin = async () => {
    const cleanEmail = email.trim().toLowerCase();
    if (!password) {
      setErr("Please enter your password");
      return;
    }
    setLoading(true);
    setErr("");
    setResendMsg("");
    setNeedsVerification(false);
    try {
      const res = await api<{ token: string; user: any }>("/auth/login", {
        method: "POST",
        body: { email: cleanEmail, password },
        auth: false,
      });
      await setToken(res.token);
      const u = res.user;
      if (!u.goal || !u.weight_kg || !u.height_cm) {
        router.replace("/onboarding");
      } else {
        router.replace("/(tabs)");
      }
    } catch (e: any) {
      if (e.status === 403) {
        setErr("Email not verified. Check your inbox for the verification link.");
        setNeedsVerification(true);
        const remaining = getVerificationCooldownSync(cleanEmail);
        if (remaining > 0) {
          setCooldown(remaining);
        }
      } else {
        setErr(e.message || "Invalid password. Please try again.");
        setNeedsVerification(false);
      }
    } finally {
      setLoading(false);
    }
  };

  // ── Step 2B: New User Signup ─────────────────────────────────
  const handleSignup = async () => {
    const cleanEmail = email.trim().toLowerCase();
    if (password.length < 8) {
      setErr("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    setErr("");
    await clearToken();
    try {
      await api<{ ok: boolean; message: string; email: string }>("/auth/signup", {
        method: "POST",
        body: { email: cleanEmail, password, name: name.trim() || undefined },
        auth: false,
      });
      await startVerificationCooldown(cleanEmail, 60);
      router.replace({ pathname: "/check-email" as any, params: { email: cleanEmail } });
    } catch (e: any) {
      setErr(e.message || "Signup failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── Suggest Strong Password ──────────────────────────────────
  const handleSuggestPassword = async () => {
    try {
      const res = await api<{ password: string }>("/auth/suggest-password", { auth: false });
      setPassword(res.password);
    } catch {
      setPassword("Crack@" + Math.random().toString(36).slice(-8) + "!");
    }
  };

  // ── Resend Verification Email ────────────────────────────────
  const resendVerification = async () => {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || cooldown > 0 || resending) return;
    setResending(true);
    setResendMsg("");
    try {
      const res = await api<{ ok: boolean; message: string; cooldown?: boolean; retry_after?: number }>(
        "/auth/resend-verification",
        {
          method: "POST",
          body: { email: cleanEmail },
          auth: false,
        }
      );
      const retrySec = res.retry_after && res.retry_after > 0 ? res.retry_after : 60;
      await startVerificationCooldown(cleanEmail, retrySec);
      setCooldown(retrySec);
      if (res.cooldown && res.retry_after) {
        setResendMsg(res.message || `Please wait ${res.retry_after}s before requesting a new link.`);
      } else {
        setResendMsg("Verification email sent! Check your inbox and spam folder.");
      }
    } catch (e: any) {
      setResendMsg(e.message || "Could not resend. Try again in a moment.");
    } finally {
      setResending(false);
    }
  };

  const handleEditEmail = () => {
    setStep("email");
    setPassword("");
    setErr("");
    setResendMsg("");
    setNeedsVerification(false);
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

          {/* ── PHASE 1: ENTER EMAIL ────────────────────────── */}
          {step === "email" ? (
            <>
              <Text style={styles.h1}>Get started</Text>
              <Text style={styles.sub}>Enter your email to sign in or create an account</Text>

              <Text style={styles.label}>Email</Text>
              <TextInput
                testID="auth-email-input"
                style={styles.input}
                placeholder="you@example.com"
                placeholderTextColor={colors.muted}
                autoCapitalize="none"
                keyboardType="email-address"
                autoCorrect={false}
                value={email}
                onChangeText={setEmail}
                onSubmitEditing={handleContinueEmail}
              />

              {err ? <Text style={styles.err}>{err}</Text> : null}

              <Pressable
                testID="auth-continue-button"
                onPress={handleContinueEmail}
                disabled={loading}
                style={({ pressed }) => [styles.btn, (pressed || loading) && { opacity: 0.85 }]}
              >
                {loading ? (
                  <ActivityIndicator color={colors.onBrand} />
                ) : (
                  <Text style={styles.btnTxt}>Continue</Text>
                )}
              </Pressable>
            </>
          ) : null}

          {/* ── PHASE 2A: EXISTING USER LOGIN ───────────────── */}
          {step === "login" ? (
            <>
              <Text style={styles.h1}>
                {userName ? `Welcome back, ${userName}!` : "Welcome back!"}
              </Text>
              
              {/* Email Pill with Edit link */}
              <View style={styles.emailPill}>
                <Text style={styles.emailPillText}>{email.trim().toLowerCase()}</Text>
                <Pressable onPress={handleEditEmail}>
                  <Text style={styles.emailPillEdit}>Edit</Text>
                </Pressable>
              </View>

              <Text style={styles.sub}>Enter your password to log in</Text>

              <Text style={styles.label}>Password</Text>
              <TextInput
                testID="login-password-input"
                style={styles.input}
                placeholder="••••••••"
                placeholderTextColor={colors.muted}
                secureTextEntry
                autoFocus
                value={password}
                onChangeText={setPassword}
                onSubmitEditing={handleLogin}
              />

              <Pressable
                testID="login-forgot-password-link"
                onPress={() => router.push({ pathname: "/forgot-password" as any, params: { email: email.trim().toLowerCase() } })}
                style={styles.forgotWrap}
              >
                <Text style={styles.forgotTxt}>Forgot password?</Text>
              </Pressable>

              {err ? <Text style={styles.err}>{err}</Text> : null}

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

              {resendMsg ? <Text style={styles.info}>{resendMsg}</Text> : null}

              <Pressable
                testID="login-submit-button"
                onPress={handleLogin}
                disabled={loading}
                style={({ pressed }) => [styles.btn, (pressed || loading) && { opacity: 0.85 }]}
              >
                {loading ? (
                  <ActivityIndicator color={colors.onBrand} />
                ) : (
                  <Text style={styles.btnTxt}>Log in</Text>
                )}
              </Pressable>
            </>
          ) : null}

          {/* ── PHASE 2B: NEW USER SIGNUP ──────────────────── */}
          {step === "signup" ? (
            <>
              <Text style={styles.h1}>Create account</Text>

              {/* Email Pill with Edit link */}
              <View style={styles.emailPill}>
                <Text style={styles.emailPillText}>{email.trim().toLowerCase()}</Text>
                <Pressable onPress={handleEditEmail}>
                  <Text style={styles.emailPillEdit}>Edit</Text>
                </Pressable>
              </View>

              <Text style={styles.sub}>Looks like you're new! Finish setting up your account</Text>

              <Text style={styles.label}>Name</Text>
              <TextInput
                testID="signup-name-input"
                style={styles.input}
                placeholder="Your name"
                placeholderTextColor={colors.muted}
                value={name}
                onChangeText={setName}
              />

              {/* Header row with Label on left, Suggest link on right */}
              <View style={styles.passwordHeaderRow}>
                <Text style={styles.label}>Password</Text>
                <Pressable testID="signup-suggest-password" onPress={handleSuggestPassword}>
                  <Text style={styles.suggestLink}>Suggest strong password</Text>
                </Pressable>
              </View>

              <TextInput
                testID="signup-password-input"
                style={styles.input}
                placeholder="At least 8 characters"
                placeholderTextColor={colors.muted}
                secureTextEntry
                value={password}
                onChangeText={setPassword}
                onSubmitEditing={handleSignup}
              />

              {err ? <Text style={styles.err}>{err}</Text> : null}

              <Pressable
                testID="signup-submit-button"
                onPress={handleSignup}
                disabled={loading}
                style={({ pressed }) => [styles.btn, (pressed || loading) && { opacity: 0.85 }]}
              >
                {loading ? (
                  <ActivityIndicator color={colors.onBrand} />
                ) : (
                  <Text style={styles.btnTxt}>Create account</Text>
                )}
              </Pressable>

              <Text style={styles.legal}>
                By creating an account you agree to our{" "}
                <Text style={styles.legalLink} onPress={() => router.push("/terms")}>Terms</Text>
                {" "}and{" "}
                <Text style={styles.legalLink} onPress={() => router.push("/privacy")}>Privacy Policy</Text>.
              </Text>
            </>
          ) : null}
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
  emailPill: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.surface2,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    borderRadius: radius.sm,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
  },
  emailPillText: {
    color: colors.onSurface,
    fontSize: 14,
    fontWeight: "600",
  },
  emailPillEdit: {
    color: colors.brand,
    fontSize: 13,
    fontWeight: "700",
  },
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
  passwordHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: spacing.md,
  },
  suggestLink: {
    color: colors.brand,
    fontSize: 13,
    fontWeight: "700",
  },
  forgotWrap: { alignSelf: "flex-end", marginTop: spacing.sm, paddingVertical: 4 },
  forgotTxt: { color: colors.brand, fontSize: 13, fontWeight: "600" },
  err: { color: colors.error, marginTop: spacing.md, fontSize: 13 },
  info: { color: colors.brand, marginTop: spacing.md, fontSize: 13 },
  legal: {
    marginTop: spacing.lg,
    fontSize: 12,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 18,
  },
  legalLink: { color: colors.brand, fontWeight: "700", textDecorationLine: "underline" },
});
