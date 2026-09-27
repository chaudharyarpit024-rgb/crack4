import { useState, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Animated,
  Easing,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, radius } from "@/src/theme";

export default function SessionExpired() {
  const router = useRouter();
  const [fadeAnim] = useState(new Animated.Value(0));
  const [slideAnim] = useState(new Animated.Value(30));

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 600,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 600,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  return (
    <SafeAreaView style={styles.wrap}>
      <Animated.View
        style={[
          styles.content,
          { opacity: fadeAnim, transform: [{ translateY: slideAnim }] },
        ]}
      >
        <View style={styles.iconCircle}>
          <View style={styles.iconGlow} />
          <Ionicons name="time-outline" size={56} color={colors.info} />
        </View>

        <Text style={styles.title}>Session Expired</Text>
        <Text style={styles.subtitle}>
          Your session has timed out for security.{"\n"}
          Please log in again to continue.
        </Text>

        <Pressable
          testID="session-expired-login"
          onPress={() => router.replace("/login")}
          style={({ pressed }) => [
            styles.loginBtn,
            pressed && { opacity: 0.85 },
          ]}
        >
          <Ionicons
            name="log-in-outline"
            size={20}
            color={colors.onBrand}
            style={{ marginRight: spacing.sm }}
          />
          <Text style={styles.loginTxt}>Log In</Text>
        </Pressable>

        <View style={styles.securityNote}>
          <Ionicons name="shield-checkmark-outline" size={16} color={colors.success} />
          <Text style={styles.securityText}>
            Sessions expire automatically to keep your account safe.
          </Text>
        </View>
      </Animated.View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  content: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  iconCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: "rgba(59, 130, 246, 0.08)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xl,
  },
  iconGlow: {
    position: "absolute",
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: "rgba(59, 130, 246, 0.12)",
  },
  title: {
    fontSize: 28,
    fontWeight: "800",
    color: colors.onSurface,
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: 15,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 22,
    marginBottom: spacing.xxl,
    maxWidth: 300,
  },
  loginBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.brand,
    paddingVertical: 14,
    paddingHorizontal: spacing.xxl,
    borderRadius: radius.md,
    marginBottom: spacing.xxl,
  },
  loginTxt: {
    color: colors.onBrand,
    fontSize: 16,
    fontWeight: "700",
  },
  securityNote: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(34, 197, 94, 0.06)",
    borderRadius: radius.md,
    padding: spacing.lg,
    maxWidth: 340,
    gap: spacing.sm,
  },
  securityText: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 20,
    flex: 1,
  },
});
