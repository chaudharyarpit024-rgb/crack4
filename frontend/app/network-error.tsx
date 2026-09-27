import { useEffect, useState } from "react";
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
import { isConnected, onConnectivityChange } from "@/src/utils/network";

export default function NetworkError() {
  const router = useRouter();
  const [checking, setChecking] = useState(false);
  const [pulseAnim] = useState(new Animated.Value(1));
  const [rotateAnim] = useState(new Animated.Value(0));

  // Subtle pulse animation on the icon
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.08,
          duration: 1200,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 1200,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, []);

  // Auto-reconnect: watch for connectivity to come back
  useEffect(() => {
    const unsub = onConnectivityChange(async (connected) => {
      if (connected) {
        // Connection restored — go back to the splash/index to re-check auth
        router.replace("/");
      }
    });
    return unsub;
  }, []);

  const spinRetry = () => {
    Animated.timing(rotateAnim, {
      toValue: 1,
      duration: 600,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start(() => rotateAnim.setValue(0));
  };

  const retry = async () => {
    setChecking(true);
    spinRetry();
    const connected = await isConnected();
    if (connected) {
      router.replace("/");
    } else {
      setChecking(false);
    }
  };

  const spin = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });

  return (
    <SafeAreaView style={styles.wrap}>
      <View style={styles.content}>
        {/* Glowing circle behind icon */}
        <Animated.View
          style={[styles.iconCircle, { transform: [{ scale: pulseAnim }] }]}
        >
          <View style={styles.iconGlow} />
          <Ionicons name="cloud-offline-outline" size={56} color={colors.warning} />
        </Animated.View>

        <Text style={styles.title}>No Connection</Text>
        <Text style={styles.subtitle}>
          We can't reach our servers right now.{"\n"}
          Check your Wi-Fi or cellular data and try again.
        </Text>

        {/* Retry button */}
        <Pressable
          testID="network-error-retry"
          onPress={retry}
          disabled={checking}
          style={({ pressed }) => [
            styles.retryBtn,
            (pressed || checking) && { opacity: 0.8 },
          ]}
        >
          <Animated.View style={{ transform: [{ rotate: spin }] }}>
            <Ionicons
              name="refresh-outline"
              size={20}
              color={colors.onBrand}
              style={{ marginRight: spacing.sm }}
            />
          </Animated.View>
          <Text style={styles.retryTxt}>
            {checking ? "Checking…" : "Try Again"}
          </Text>
        </Pressable>

        {/* Helpful tips */}
        <View style={styles.tipsCard}>
          <Text style={styles.tipsTitle}>Things to try</Text>
          {[
            "Turn Wi-Fi off and back on",
            "Switch to cellular data",
            "Move closer to your router",
            "Restart the app",
          ].map((tip, i) => (
            <View key={i} style={styles.tipRow}>
              <Text style={styles.tipBullet}>•</Text>
              <Text style={styles.tipText}>{tip}</Text>
            </View>
          ))}
        </View>
      </View>
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
    backgroundColor: "rgba(245, 158, 11, 0.08)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xl,
  },
  iconGlow: {
    position: "absolute",
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: "rgba(245, 158, 11, 0.12)",
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
  retryBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.brand,
    paddingVertical: 14,
    paddingHorizontal: spacing.xxl,
    borderRadius: radius.md,
    marginBottom: spacing.xxl,
  },
  retryTxt: {
    color: colors.onBrand,
    fontSize: 16,
    fontWeight: "700",
  },
  tipsCard: {
    backgroundColor: colors.surface2,
    borderRadius: radius.lg,
    padding: spacing.xl,
    width: "100%",
    maxWidth: 340,
  },
  tipsTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: colors.onSurface2,
    marginBottom: spacing.md,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  tipRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: spacing.sm,
  },
  tipBullet: {
    color: colors.warning,
    fontSize: 16,
    fontWeight: "700",
    marginRight: spacing.sm,
    lineHeight: 22,
  },
  tipText: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 22,
    flex: 1,
  },
});
