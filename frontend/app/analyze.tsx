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

type UnitType = "g" | "oz" | "servings";

export default function Analyze() {
  const router = useRouter();
  const { b64 } = useLocalSearchParams<{ b64: string }>();
  const [result, setResult] = useState<Analysis | null>(null);
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  // Exact amount state
  const [unit, setUnit] = useState<UnitType>("g");
  const [amountStr, setAmountStr] = useState<string>("150");

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
        setAmountStr(String(Math.round(baseG)));
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

  const baseGrams = result?.serving_size_g || 150;
  const numAmount = parseFloat(amountStr) || 0;

  // Calculate equivalent grams based on unit selection
  let currentGrams = numAmount;
  if (unit === "oz") {
    currentGrams = numAmount * 28.3495;
  } else if (unit === "servings") {
    currentGrams = numAmount * baseGrams;
  }

  const ratio = baseGrams > 0 ? currentGrams / baseGrams : 1;
  const calcCalories = result ? Math.max(0, Math.round(result.calories * ratio)) : 0;
  const calcFat = result ? Math.max(0, Math.round(result.fat_g * ratio * 10) / 10) : 0;
  const calcCarbs = result ? Math.max(0, Math.round(result.carbs_g * ratio * 10) / 10) : 0;
  const calcProtein = result ? Math.max(0, Math.round(result.protein_g * ratio * 10) / 10) : 0;

  const handleUnitChange = (newUnit: UnitType) => {
    Haptics.selectionAsync();
    if (newUnit === unit) return;

    // Convert existing input value to match new unit
    let valInGrams = numAmount;
    if (unit === "oz") valInGrams = numAmount * 28.3495;
    if (unit === "servings") valInGrams = numAmount * baseGrams;

    if (newUnit === "g") {
      setAmountStr(String(Math.round(valInGrams)));
    } else if (newUnit === "oz") {
      setAmountStr(String(parseFloat((valInGrams / 28.3495).toFixed(1))));
    } else if (newUnit === "servings") {
      const s = baseGrams > 0 ? valInGrams / baseGrams : 1;
      setAmountStr(String(parseFloat(s.toFixed(2))));
    }
    setUnit(newUnit);
  };

  const adjustAmount = (delta: number) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const nextVal = Math.max(0, numAmount + delta);
    setAmountStr(unit === "servings" ? String(parseFloat(nextVal.toFixed(2))) : String(Math.round(nextVal)));
  };

  const setMultiplier = (mult: number) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    const targetGrams = baseGrams * mult;
    if (unit === "g") {
      setAmountStr(String(Math.round(targetGrams)));
    } else if (unit === "oz") {
      setAmountStr(String(parseFloat((targetGrams / 28.3495).toFixed(1))));
    } else if (unit === "servings") {
      setAmountStr(String(mult));
    }
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

            {/* Exact Food Amount & Portion Control Feature */}
            <View style={styles.amountCard} testID="exact-amount-section">
              <View style={styles.amountHeader}>
                <Ionicons name="scale-outline" size={20} color={colors.brand} />
                <Text style={styles.amountTitle}>Exact Food Amount</Text>
              </View>
              <Text style={styles.amountSubtitle}>Adjust weight or serving size for precise calories</Text>

              {/* Unit Toggle Tabs */}
              <View style={styles.unitTabs}>
                <Pressable
                  testID="unit-toggle-g"
                  onPress={() => handleUnitChange("g")}
                  style={[styles.unitTab, unit === "g" && styles.unitTabActive]}
                >
                  <Text style={[styles.unitTabTxt, unit === "g" && styles.unitTabTxtActive]}>Grams (g)</Text>
                </Pressable>
                <Pressable
                  testID="unit-toggle-oz"
                  onPress={() => handleUnitChange("oz")}
                  style={[styles.unitTab, unit === "oz" && styles.unitTabActive]}
                >
                  <Text style={[styles.unitTabTxt, unit === "oz" && styles.unitTabTxtActive]}>Ounces (oz)</Text>
                </Pressable>
                <Pressable
                  testID="unit-toggle-servings"
                  onPress={() => handleUnitChange("servings")}
                  style={[styles.unitTab, unit === "servings" && styles.unitTabActive]}
                >
                  <Text style={[styles.unitTabTxt, unit === "servings" && styles.unitTabTxtActive]}>Servings</Text>
                </Pressable>
              </View>

              {/* Input row with Stepper controls */}
              <View style={styles.inputRow}>
                <Pressable
                  testID="amount-minus"
                  onPress={() => adjustAmount(unit === "servings" ? -0.25 : unit === "oz" ? -1 : -10)}
                  style={styles.stepBtn}
                >
                  <Ionicons name="remove" size={20} color={colors.onSurface} />
                </Pressable>

                <View style={styles.inputContainer}>
                  <TextInput
                    testID="exact-amount-input"
                    style={styles.amountInput}
                    keyboardType="decimal-pad"
                    value={amountStr}
                    onChangeText={setAmountStr}
                    selectTextOnFocus
                  />
                  <Text style={styles.unitLabel}>{unit}</Text>
                </View>

                <Pressable
                  testID="amount-plus"
                  onPress={() => adjustAmount(unit === "servings" ? 0.25 : unit === "oz" ? 1 : 10)}
                  style={styles.stepBtn}
                >
                  <Ionicons name="add" size={20} color={colors.onSurface} />
                </Pressable>
              </View>

              {/* Multiplier Presets */}
              <View style={styles.presetRow}>
                {[0.5, 1.0, 1.5, 2.0].map((m) => (
                  <Pressable
                    key={m}
                    testID={`preset-${m}`}
                    onPress={() => setMultiplier(m)}
                    style={styles.presetBtn}
                  >
                    <Text style={styles.presetTxt}>{m}x</Text>
                  </Pressable>
                ))}
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
  unitTabs: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: 3,
    marginBottom: spacing.md,
  },
  unitTab: {
    flex: 1,
    paddingVertical: 8,
    alignItems: "center",
    borderRadius: radius.sm,
  },
  unitTabActive: {
    backgroundColor: colors.brand,
  },
  unitTabTxt: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.muted,
  },
  unitTabTxtActive: {
    color: colors.onBrand,
    fontWeight: "700",
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
    marginVertical: spacing.sm,
  },
  stepBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    borderWidth: 1.5,
    borderColor: colors.brand,
    minWidth: 140,
    justifyContent: "center",
  },
  amountInput: {
    fontSize: 22,
    fontWeight: "800",
    color: colors.onSurface,
    paddingVertical: 10,
    textAlign: "center",
    minWidth: 60,
  },
  unitLabel: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.muted,
    marginLeft: 6,
  },
  presetRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.md,
    gap: 8,
  },
  presetBtn: {
    flex: 1,
    paddingVertical: 8,
    backgroundColor: colors.surface,
    borderRadius: radius.sm,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  presetTxt: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.brand,
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
