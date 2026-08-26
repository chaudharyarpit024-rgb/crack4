import { useState } from "react";
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

export default function ResetPassword() {
  const router = useRouter();
  const params = useLocalSearchParams<{ token?: string | string[] }>();
  const token = Array.isArray(params.token) ? params.token[0] : params.token || "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const submit = async () => {
    if (!token) {
      setErr("Invalid or missing reset link. Please request a new link.");
      return;
    }
    if (!password || !confirmPassword) {
      setErr("Please fill in both password fields.");
      return;
    }
    if (password.length < 8) {
      setErr("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setErr("Passwords do not match.");
      return;
    }

    setLoading(true);
    setErr("");
    try {
      await api<{ ok: boolean; message: string }>("/auth/reset-password", {
        method: "POST",
        body: { token, new_password: password },
        auth: false,
      });
      setSuccess(true);
      setTimeout(() => {
        router.replace("/login");
      }, 2000);
    } catch (e: any) {
      setErr(e.message || "Failed to reset password. The link may have expired.");
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

          {success ? (
            <View style={styles.successWrap}>
              <View style={styles.iconCircle}>
                <Text style={styles.iconTxt}>✓</Text>
              </View>
              <Text style={styles.h1}>Password Reset!</Text>
              <Text style={styles.sub}>
                Your password has been updated successfully. Redirecting you to login…
              </Text>
              <Pressable
                testID="reset-password-go-login"
                onPress={() => router.replace("/login")}
                style={styles.btn}
              >
                <Text style={styles.btnTxt}>Go to Login</Text>
              </Pressable>
            </View>
          ) : (
            <>
              <Text style={styles.h1}>Set New Password</Text>
              <Text style={styles.sub}>
                Enter and confirm your new password (at least 8 characters).
              </Text>

              {!token ? (
                <View style={{ marginTop: spacing.lg }}>
                  <Text style={styles.err}>
                    Invalid or missing reset token. Please request a new password reset link.
                  </Text>
                  <Pressable
                    onPress={() => router.replace("/forgot-password" as any)}
                    style={[styles.btn, { marginTop: spacing.lg }]}
                  >
                    <Text style={styles.btnTxt}>Request New Link</Text>
                  </Pressable>
                </View>
              ) : (
                <>
                  <Text style={styles.label}>New Password</Text>
                  <TextInput
                    testID="reset-password-input"
                    style={styles.input}
                    placeholder="At least 8 characters"
                    placeholderTextColor={colors.muted}
                    secureTextEntry
                    value={password}
                    onChangeText={(t) => {
                      setPassword(t);
                      setErr("");
                    }}
                  />

                  <Text style={styles.label}>Confirm New Password</Text>
                  <TextInput
                    testID="reset-confirm-password-input"
                    style={styles.input}
                    placeholder="Repeat new password"
                    placeholderTextColor={colors.muted}
                    secureTextEntry
                    value={confirmPassword}
                    onChangeText={(t) => {
                      setConfirmPassword(t);
                      setErr("");
                    }}
                  />

                  {err ? (
                    <Text style={styles.err} testID="reset-password-error">
                      {err}
                    </Text>
                  ) : null}

                  <Pressable
                    testID="reset-password-submit-button"
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
                      <Text style={styles.btnTxt}>Update Password</Text>
                    )}
                  </Pressable>

                  <Pressable
                    onPress={() => router.replace("/login")}
                    style={{ marginTop: spacing.xl }}
                  >
                    <Text style={styles.link}>
                      Back to <Text style={{ color: colors.brand, fontWeight: "700" }}>Login</Text>
                    </Text>
                  </Pressable>
                </>
              )}
            </>
          )}
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
  link: { textAlign: "center", color: colors.muted, fontSize: 14 },
  successWrap: { alignItems: "center", marginTop: spacing.lg },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "rgba(76, 175, 80, 0.15)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  iconTxt: { fontSize: 32, color: "#4caf50", fontWeight: "700" },
});
