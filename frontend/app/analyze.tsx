import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  Image,
  ScrollView,
  TextInput,
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
  serving_size_g?: number;
  verdict: "good" | "bad" | "ok";
  reason: string;
};

export default function Analyze() {
  const router = useRouter();
  const { b64 } = useLocalSearchParams<{ b64: string }>();
  const [result, setResult] = useState<Analysis | null>(null);
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  // Simple direct weight typing (in grams)
  const [weightStr, setWeightStr] = useState<string>("150");

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
        const baseG = r.serving_size_g || 150;
        setWeightStr(String(Math.round(baseG)));
      } catch (e: any) {
        const msg: string = e.message || "Analysis failed";
        const status: number | undefined = e.status ?? e.statusCode;
        // 402 → subscription required or daily trial limit hit
        if (status === 402 || msg.toLowerCase().includes("subscription") || msg.includes("402")) {
          const reason = msg.toLowerCase().includes("daily") ? "trial-limit" : "trial-ended";
          router.replace({ pathname: "/subscribe", params: { reason } });
          return;
        }
        // 429 → paid monthly quota exhausted
        if (status === 429 || msg.includes("429")) {
          setErr("Monthly scan limit reached (500/500). Your quota resets on your next billing cycle.");
          return;
        }
        // 413 → image too large (client-side guard should prevent this, but be safe)
        if (status === 413 || msg.includes("413") || msg.toLowerCase().includes("too large")) {
          setErr("Image is too large. Please try again — the camera will compress it automatically.");
          return;
        }
        setErr(msg);
      }
    })();
  }, [b64]);

  const baseGrams = result?.serving_size_g || 150;
  const currentGrams = Math.max(0, parseFloat(weightStr) || 0);

  const ratio = baseGrams > 0 ? currentGrams / baseGrams : 1;
  const calcCalories = result ? Math.max(0, Math.round(result.calories * ratio)) : 0;
  const calcFat = result ? Math.max(0, Math.round(result.fat_g * ratio * 10) / 10) : 0;
  const calcCarbs = result ? Math.max(0, Math.round(result.carbs_g * ratio * 10) / 10) : 0;
  const calcProtein = result ? Math.max(0, Math.round(result.protein_g * ratio * 10) / 10) : 0;

  const setQuickWeight = (grams: number) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setWeightStr(String(Math.round(grams)));
  };

  const logIt = async () => {
    if (!result) return;
    setSaving(true);
    try {
      await api("/food/log", {
        method: "POST",
        body: {
          food_name: result.food_name,
          calories: calcCalories,
          fat_g: calcFat,
          carbs_g: calcCarbs,
          protein_g: calcProtein,
          serving_size_g: Math.round(currentGrams),
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

  // Pre-calculated convenient portion options
  const halfPortion = Math.round(baseGrams * 0.5);
  const fullPortion = Math.round(baseGrams);
  const oneHalfPortion = Math.round(baseGrams * 1.5);
  const doublePortion = Math.round(baseGrams * 2);

  return (
    <SafeAreaView style={styles.wrap} edges={["top"]}>
      <View style={styles.header}>
        <Pressable testID="analyze-close" onPress={() => router.replace("/(tabs)")} style={styles.iconBtn}>
          <Ionicons name="close" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>AI analysis</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
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
                <Text style={styles.calorieVal} testID="analysis-calories">{calcCalories}</Text>
                <Text style={styles.calorieUnit}>calories ({Math.round(currentGrams)}g portion)</Text>
              </View>

              <View style={styles.macros}>
                <View style={styles.macro}>
                  <Text style={styles.macroVal} testID="analysis-fat">{calcFat}g</Text>
                  <Text style={styles.macroLabel}>Fat</Text>
                </View>
                <View style={styles.macroDivider} />
                <View style={styles.macro}>
                  <Text style={styles.macroVal} testID="analysis-carbs">{calcCarbs}g</Text>
                  <Text style={styles.macroLabel}>Carbs</Text>
                </View>
                <View style={styles.macroDivider} />
                <View style={styles.macro}>
                  <Text style={styles.macroVal} testID="analysis-protein">{calcProtein}g</Text>
                  <Text style={styles.macroLabel}>Protein</Text>
                </View>
              </View>
            </View>

            {/* Simple, User-Friendly Food Weight Card */}
            <View style={styles.amountCard} testID="exact-amount-section">
              <View style={styles.amountHeader}>
                <Ionicons name="scale-outline" size={20} color={colors.brand} />
                <Text style={styles.amountTitle}>Portion Weight</Text>
              </View>
              <Text style={styles.amountSubtitle}>Type your weight in grams to calculate exact calories</Text>

              {/* Direct Weight Input Box */}
              <View style={styles.weightInputRow}>
                <TextInput
                  testID="exact-amount-input"
                  style={styles.weightInput}
                  keyboardType="numeric"
                  value={weightStr}
                  onChangeText={setWeightStr}
                  placeholder="0"
                  placeholderTextColor={colors.muted}
                  selectTextOnFocus
                />
                <Text style={styles.gramsLabel}>grams</Text>
              </View>

              {/* Quick-select Weight Chips */}
              <View style={styles.chipsRow}>
                {[
                  { label: "½ Portion", g: halfPortion },
                  { label: "1 Portion", g: fullPortion },
                  { label: "1.5x", g: oneHalfPortion },
                  { label: "2x", g: doublePortion },
                ].map((chip) => {
                  const isSelected = Math.round(currentGrams) === chip.g;
                  return (
                    <Pressable
                      key={chip.label}
                      onPress={() => setQuickWeight(chip.g)}
                      style={[styles.chip, isSelected && styles.chipActive]}
                    >
                      <Text style={[styles.chipTxt, isSelected && styles.chipTxtActive]}>
                        {chip.label} ({chip.g}g)
                      </Text>
                    </Pressable>
                  );
                })}
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
  calorieUnit: { fontSize: 13, color: colors.muted, textTransform: "uppercase", letterSpacing: 1.5, marginTop: 2 },
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
  amountCard: {
    marginTop: spacing.md,
    padding: spacing.lg,
    backgroundColor: colors.surface2,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  amountHeader: { flexDirection: "row", alignItems: "center", gap: 8 },
  amountTitle: { fontSize: 16, fontWeight: "700", color: colors.onSurface },
  amountSubtitle: { fontSize: 12, color: colors.muted, marginTop: 4, marginBottom: spacing.md },
  weightInputRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: 4,
    borderWidth: 1.5,
    borderColor: colors.brand,
    marginVertical: spacing.xs,
  },
  weightInput: {
    fontSize: 28,
    fontWeight: "900",
    color: colors.onSurface,
    paddingVertical: 10,
    textAlign: "center",
    minWidth: 80,
  },
  gramsLabel: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.muted,
    marginLeft: 8,
  },
  chipsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: spacing.md,
    justifyContent: "space-between",
  },
  chip: {
    flexBasis: "48%",
    paddingVertical: 10,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.brand + "22",
    borderColor: colors.brand,
  },
  chipTxt: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.muted,
  },
  chipTxtActive: {
    color: colors.brand,
    fontWeight: "800",
  },
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

