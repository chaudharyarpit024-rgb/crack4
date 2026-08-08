import { useEffect } from "react";
import { View, Text, StyleSheet, ActivityIndicator } from "react-native";
import { useRouter } from "expo-router";
import { api } from "@/src/api";
import { colors, spacing } from "@/src/theme";

export default function Index() {
  const router = useRouter();

  useEffect(() => {
    (async () => {
      try {
        const me = await api<any>("/auth/me");
        if (!me.goal || !me.weight_kg || !me.height_cm) {
          router.replace("/onboarding");
        } else {
          router.replace("/(tabs)");
        }
      } catch {
        router.replace("/login");
      }
    })();
  }, []);

  return (
    <View style={styles.wrap} testID="splash-screen">
      <Text style={styles.brand}>CRACK</Text>
      <Text style={styles.tag}>Track It First</Text>
      <ActivityIndicator color={colors.brand} style={{ marginTop: spacing.xl }} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  brand: {
    fontSize: 48,
    fontWeight: "900",
    color: colors.brand,
    letterSpacing: 4,
  },
  tag: {
    marginTop: spacing.sm,
    fontSize: 14,
    color: colors.muted,
    letterSpacing: 2,
    textTransform: "uppercase",
  },
});
