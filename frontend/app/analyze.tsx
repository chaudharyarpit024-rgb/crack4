import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  Image,
  ScrollView,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { colors, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";

type Analysis = {
  food_name: string;
  calories: number;
  fat_g: number;
  carbs_g: number;
  protein_g: number;
  verdict: "good" | "bad" | "ok";
  reason: string;
};

export default function Analyze() {
  const router = useRouter();
  const { b64 } = useLocalSearchParams<{ b64: string }>();
  const [result, setResult] = useState<Analysis | null>(null);
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!b64) {
      setErr("No image");
      return;
    }
    (async () => {
      try {
        const r = await api<Analysis>("/food/analyze", {
          method: "POST",
          body: { image_base64: b64 },
        });
        setResult(r);
      } catch (e: any) {
        const msg = e.message || "Analysis failed";
        if (msg.toLowerCase().includes("subscription") || msg.includes("402")) {
          router.replace({ pathname: "/subscribe", params: { reason: "trial-ended" } });
          return;
        }
        setErr(msg);
      }
    })();
  }, [b64]);

  const logIt = async () => {
    if (!result) return;
    setSaving(true);
    try {
      await api("/food/log", {
        method: "POST",
        body: {
          food_name: result.food_name,
          calories: result.calories,
          fat_g: result.fat_g,
          carbs_g: result.carbs_g,
          protein_g: result.protein_g,
          source: "ai",
        },
      });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.replace("/(tabs)");
    } catch {
      setSaving(false);
    }
  };

  const verdictColor =
    result?.verdict === "good" ? colors.success : result?.verdict === "bad" ? colors.error : colors.warning;
  const verdictLabel =
    result?.verdict === "good" ? "Good to eat" : result?.verdict === "bad" ? "Better skip" : "Okay in moderation";

  return (
    <SafeAreaView style={styles.wrap} edges={["top"]}>
      <View style={styles.header}>
        <Pressable testID="analyze-close" onPress={() => router.replace("/(tabs)")} style={styles.iconBtn}>
          <Ionicons name="close" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>AI analysis</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        {b64 ? (
          <Image
            source={{ uri: `data:image/jpeg;base64,${b64}` }}
            style={styles.photo}
            resizeMode="cover"
          />
        ) : null}

        {!result && !err ? (
          <View style={styles.loading}>
            <ActivityIndicator color={colors.brand} size="large" />
            <Text style={styles.loadingTxt}>Analyzing your food…</Text>
            <Text style={styles.loadingSub}>Estimating calories, fat, and carbs</Text>
          </View>
        ) : null}

        {err ? (
          <View style={styles.errBox}>
            <Ionicons name="warning-outline" size={32} color={colors.error} />
            <Text style={styles.errTxt}>{err}</Text>
            <Pressable
              testID="analyze-manual"
              onPress={() => router.replace("/manual")}
              style={styles.btnGhost}
            >
              <Text style={styles.btnGhostTxt}>Enter manually</Text>
            </Pressable>
          </View>
        ) : null}

        {result ? (
          <>
            <View style={styles.card}>
              <View style={styles.rowBetween}>
                <Text style={styles.foodName} testID="analysis-food-name">{result.food_name}</Text>
                <View style={[styles.verdict, { backgroundColor: verdictColor + "22" }]}>
                  <View style={[styles.dot, { backgroundColor: verdictColor }]} />
                  <Text style={[styles.verdictTxt, { color: verdictColor }]}>{verdictLabel}</Text>
                </View>
              </View>
              {result.reason ? <Text style={styles.reason}>{result.reason}</Text> : null}

              <View style={styles.calorieBig}>
                <Text style={styles.calorieVal} testID="analysis-calories">{Math.round(result.calories)}</Text>
                <Text style={styles.calorieUnit}>calories</Text>
              </View>

              <View style={styles.macros}>
                <View style={styles.macro}>
                  <Text style={styles.macroVal}>{Math.round(result.fat_g)}g</Text>
                  <Text style={styles.macroLabel}>Fat</Text>
                </View>
                <View style={styles.macroDivider} />
                <View style={styles.macro}>
                  <Text style={styles.macroVal}>{Math.round(result.carbs_g)}g</Text>
                  <Text style={styles.macroLabel}>Carbs</Text>
                </View>
                <View style={styles.macroDivider} />
                <View style={styles.macro}>
                  <Text style={styles.macroVal}>{Math.round(result.protein_g)}g</Text>
                  <Text style={styles.macroLabel}>Protein</Text>
                </View>
              </View>
            </View>

            <Pressable
              testID="eat-it-btn"
              onPress={logIt}
              disabled={saving}
              style={({ pressed }) => [styles.btn, (pressed || saving) && { opacity: 0.85 }]}
            >
              {saving ? (
                <ActivityIndicator color={colors.onBrand} />
              ) : (
                <>
                  <Ionicons name="checkmark-circle" size={20} color={colors.onBrand} />
                  <Text style={styles.btnTxt}>  Eating it — add to today</Text>
                </>
              )}
            </Pressable>

            <Pressable
              testID="skip-it-btn"
              onPress={() => router.replace("/(tabs)")}
              style={styles.btnGhost}
            >
              <Text style={styles.btnGhostTxt}>Not eating it</Text>
            </Pressable>
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
  },
  headerTitle: { fontSize: 16, fontWeight: "700", color: colors.onSurface },
  iconBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.surface2,
    alignItems: "center",
    justifyContent: "center",
  },
  scroll: { padding: spacing.lg, paddingBottom: spacing.xxxl },
  photo: {
    width: "100%",
    height: 220,
    borderRadius: radius.lg,
    backgroundColor: colors.surface2,
  },
  loading: { padding: spacing.xxl, alignItems: "center" },
  loadingTxt: { marginTop: spacing.lg, fontSize: 16, fontWeight: "700", color: colors.onSurface },
  loadingSub: { marginTop: spacing.xs, fontSize: 13, color: colors.muted },
  errBox: {
    marginTop: spacing.xl,
    padding: spacing.xl,
    backgroundColor: colors.surface2,
    borderRadius: radius.lg,
    alignItems: "center",
  },
  errTxt: { marginTop: spacing.md, color: colors.onSurface, textAlign: "center" },
  card: {
    marginTop: spacing.lg,
    padding: spacing.lg,
    backgroundColor: colors.surface2,
    borderRadius: radius.lg,
  },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" },
  foodName: { fontSize: 20, fontWeight: "800", color: colors.onSurface, flex: 1, marginRight: spacing.sm },
  verdict: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.pill,
  },
  dot: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  verdictTxt: { fontSize: 12, fontWeight: "700" },
  reason: { marginTop: spacing.sm, fontSize: 13, color: colors.muted, lineHeight: 18 },
  calorieBig: { marginTop: spacing.xl, alignItems: "center" },
  calorieVal: { fontSize: 48, fontWeight: "900", color: colors.brand },
  calorieUnit: { fontSize: 13, color: colors.muted, textTransform: "uppercase", letterSpacing: 2 },
  macros: {
    flexDirection: "row",
    marginTop: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    justifyContent: "space-between",
  },
  macro: { flex: 1, alignItems: "center" },
  macroVal: { fontSize: 18, fontWeight: "800", color: colors.onSurface },
  macroLabel: { fontSize: 11, color: colors.muted, textTransform: "uppercase", marginTop: 2 },
  macroDivider: { width: 1, backgroundColor: colors.border },
  btn: {
    flexDirection: "row",
    backgroundColor: colors.brand,
    paddingVertical: 16,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.lg,
  },
  btnTxt: { color: colors.onBrand, fontSize: 16, fontWeight: "700" },
  btnGhost: {
    marginTop: spacing.sm,
    paddingVertical: 14,
    borderRadius: radius.md,
    alignItems: "center",
  },
  btnGhostTxt: { color: colors.muted, fontSize: 14, fontWeight: "600" },
});
