import { useState, useEffect, useCallback } from "react";
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

export default function MaintenanceError() {
  const router = useRouter();
  const [retrying, setRetrying] = useState(false);
  const [rotateAnim] = useState(new Animated.Value(0));

  // Rotating gear animation
  const [gearAnim] = useState(new Animated.Value(0));
  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(gearAnim, {
        toValue: 1,
        duration: 4000,
        easing: Easing.linear,
        useNativeDriver: true,
      })
    );
    loop.start();
    return () => loop.stop();
  }, []);

  const gearSpin = gearAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });

  const retry = useCallback(() => {
    setRetrying(true);
    Animated.timing(rotateAnim, {
      toValue: 1,
      duration: 600,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start(() => {
      rotateAnim.setValue(0);
      router.replace("/");
    });
  }, []);

  const spin = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });

  return (
    <SafeAreaView style={styles.wrap}>
      <View style={styles.content}>
        <Animated.View
          style={[styles.iconCircle, { transform: [{ rotate: gearSpin }] }]}
        >
          <View style={styles.iconGlow} />
          <Ionicons name="construct-outline" size={56} color={colors.warning} />
        </Animated.View>

        <Text style={styles.title}>Under Maintenance</Text>
        <Text style={styles.subtitle}>
          We're making improvements to give you{"\n"}
          a better experience. Be back shortly!
        </Text>

        <Pressable
          testID="maintenance-retry"
          onPress={retry}
          disabled={retrying}
          style={({ pressed }) => [
            styles.retryBtn,
            (pressed || retrying) && { opacity: 0.8 },
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
            {retrying ? "Checking…" : "Check Again"}
          </Text>
        </Pressable>

        <View style={styles.statusCard}>
          <View style={styles.statusDot} />
          <Text style={styles.statusText}>Maintenance in progress</Text>
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
  statusCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(245, 158, 11, 0.06)",
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.warning,
  },
  statusText: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "600",
  },
});
