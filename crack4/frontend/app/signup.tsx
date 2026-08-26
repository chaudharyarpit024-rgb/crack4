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
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";

export default function Signup() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!email || !password) {
      setErr("Enter email and password");
      return;
    }
    if (password.length < 8) {
      setErr("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    setErr("");
    try {
      await api<{ ok: boolean; message: string; email: string }>("/auth/signup", {
        method: "POST",
        body: { email, password, name },
        auth: false,
      });
      router.replace({ pathname: "/check-email", params: { email } });
    } catch (e: any) {
      if (e.status === 400) {
        setErr("Email already registered. Try logging in instead.");
      } else {
        setErr(e.message || "Signup failed");
      }
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

          <Text style={styles.h1}>Create account</Text>
          <Text style={styles.sub}>Start tracking your meals today</Text>

          <Text style={styles.label}>Name</Text>
          <TextInput
            testID="signup-name-input"
            style={styles.input}
            placeholder="Your name"
            placeholderTextColor={colors.muted}
            value={name}
            onChangeText={setName}
          />
          <Text style={styles.label}>Email</Text>
          <TextInput
            testID="signup-email-input"
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
            testID="signup-password-input"
            style={styles.input}
            placeholder="At least 8 characters"
            placeholderTextColor={colors.muted}
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />

          {err ? (
            <Text style={styles.err} testID="signup-error">
              {err}
            </Text>
          ) : null}

          <Pressable
            testID="signup-submit-button"
            onPress={submit}
            disabled={loading}
            style={({ pressed }) => [styles.btn, (pressed || loading) && { opacity: 0.85 }]}
          >
            {loading ? (
              <ActivityIndicator color={colors.onBrand} />
            ) : (
              <Text style={styles.btnTxt}>Create account</Text>
            )}
          </Pressable>

          <Text style={styles.legal} testID="signup-legal">
            By creating an account you agree to our{" "}
            <Text style={styles.legalLink} onPress={() => router.push("/terms")}>Terms</Text>
            {" "}and{" "}
            <Text style={styles.legalLink} onPress={() => router.push("/privacy")}>Privacy Policy</Text>.
          </Text>

          <Pressable
            testID="go-login-link"
            onPress={() => router.replace("/login")}
            style={{ marginTop: spacing.lg }}
          >
            <Text style={styles.link}>
              Already have an account?{" "}
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
  sub: { fontSize: 14, color: colors.muted, marginTop: spacing.xs, marginBottom: spacing.xl },
  label: {
    fontSize: 13,
    color: colors.onSurface2,
    marginTop: spacing.md,
    marginBottom: spacing.xs,
    fontWeight: "600",
  },
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
  legal: {
    marginTop: spacing.lg,
    fontSize: 12,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 18,
  },
  legalLink: { color: colors.brand, fontWeight: "700", textDecorationLine: "underline" },
  link: { textAlign: "center", color: colors.muted, fontSize: 14 },
});
