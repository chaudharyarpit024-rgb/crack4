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

export default function ServerError() {
  const router = useRouter();
  const [retrying, setRetrying] = useState(false);
  const [bounceAnim] = useState(new Animated.Value(0));
  const [rotateAnim] = useState(new Animated.Value(0));

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(bounceAnim, {
          toValue: -8,
          duration: 1000,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(bounceAnim, {
          toValue: 0,
          duration: 1000,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, []);

  const retry = () => {
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
  };

  const spin = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });

  return (
    <SafeAreaView style={styles.wrap}>
      <View style={styles.content}>
        <Animated.View
          style={[styles.iconCircle, { transform: [{ translateY: bounceAnim }] }]}
        >
          <View style={styles.iconGlow} />
          <Ionicons name="server-outline" size={56} color={colors.error} />
        </Animated.View>

        <Text style={styles.title}>Something Went Wrong</Text>
        <Text style={styles.subtitle}>
          Our servers are having trouble right now.{"\n"}
          This usually fixes itself in a few moments.
        </Text>

        <Pressable
          testID="server-error-retry"
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
            {retrying ? "Retrying…" : "Try Again"}
          </Text>
        </Pressable>

        <View style={styles.infoCard}>
          <Ionicons name="information-circle-outline" size={18} color={colors.info} />
          <Text style={styles.infoText}>
            If this persists, try restarting the app or check back later.
          </Text>
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
    backgroundColor: "rgba(239, 68, 68, 0.08)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xl,
  },
  iconGlow: {
    position: "absolute",
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: "rgba(239, 68, 68, 0.12)",
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
  infoCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(59, 130, 246, 0.06)",
    borderRadius: radius.md,
    padding: spacing.lg,
    maxWidth: 340,
    gap: spacing.sm,
  },
  infoText: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 20,
    flex: 1,
  },
});
