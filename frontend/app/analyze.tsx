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

// Supported measurement units.
// For logging purposes we always send grams to the backend.
// ml is treated as 1:1 with g for calorie ratio calculation
// (water density ≈ 1 g/ml; most juices/milk/soups are within 5%).
type Unit = "g" | "ml";

const UNITS: { label: string; value: Unit }[] = [
  { label: "g", value: "g" },
  { label: "ml", value: "ml" },
];

export default function Analyze() {
  const router = useRouter();
  const { b64 } = useLocalSearchParams<{ b64: string }>();
  const [result, setResult] = useState<Analysis | null>(null);
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  // Portion state
  const [weightStr, setWeightStr] = useState<string>("150");
  const [unit, setUnit] = useState<Unit>("g");
  // When useAIEstimate is true the card collapses and the AI serving size is used directly.
  const [useAIEstimate, setUseAIEstimate] = useState(false);

  // Re-evaluation state
  const [analyzing, setAnalyzing] = useState(false);
  const [showCorrection, setShowCorrection] = useState(false);
  const [correctionText, setCorrectionText] = useState("");
  const [activeHint, setActiveHint] = useState("");

  const runAnalysis = async (hint?: string) => {
    if (!b64) {
      setErr("No image");
      setAnalyzing(false);
      return;
    }
    setAnalyzing(true);
    setErr("");
    if (hint) {
      setActiveHint(hint);
    }

    try {
      const r = await api<Analysis>("/food/analyze", {
        method: "POST",
        body: {
          image_base64: b64,
          ...(hint ? { user_hint: hint.trim() } : {}),
        },
      });
      setResult(r);
      const baseG = r.serving_size_g || 150;
      setWeightStr(String(Math.round(baseG)));
      setUseAIEstimate(true);
      setShowCorrection(false);
      setCorrectionText("");
    } catch (e: any) {
      const msg: string = e.message || "Analysis failed";
      const status: number | undefined = e.status ?? e.statusCode;
      if (status === 402 || msg.toLowerCase().includes("subscription") || msg.includes("402")) {
        const reason = msg.toLowerCase().includes("daily") ? "trial-limit" : "trial-ended";
        router.replace({ pathname: "/subscribe", params: { reason } });
        return;
      }
      if (status === 429 || msg.includes("429")) {
        setErr("Monthly scan limit reached (500/500). Your quota resets on your next billing cycle.");
        return;
      }
      if (status === 413 || msg.includes("413") || msg.toLowerCase().includes("too large")) {
        setErr("Image is too large. Please try again — the camera will compress it automatically.");
        return;
      }
      setErr(msg);
    } finally {
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    runAnalysis();
  }, [b64]);




  // The AI's base serving size in grams (always in grams — the AI only knows grams).
  const baseGrams = result?.serving_size_g || 150;

  // The current portion in "grams equivalent" for ratio calculation.
  // ml is 1:1 with g (density ≈ 1 g/ml for most liquids).
  const currentAmount = Math.max(0, parseFloat(weightStr) || 0);
  const effectiveGrams = useAIEstimate ? baseGrams : currentAmount;

  const ratio = baseGrams > 0 ? effectiveGrams / baseGrams : 1;
  const calcCalories = result ? Math.max(0, Math.round(result.calories * ratio)) : 0;
  const calcFat = result ? Math.max(0, Math.round(result.fat_g * ratio * 10) / 10) : 0;
  const calcCarbs = result ? Math.max(0, Math.round(result.carbs_g * ratio * 10) / 10) : 0;
  const calcProtein = result ? Math.max(0, Math.round(result.protein_g * ratio * 10) / 10) : 0;

  const setQuickAmount = (val: number) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setWeightStr(String(Math.round(val)));
    setUseAIEstimate(false);
  };

  const toggleEstimate = () => {
    Haptics.selectionAsync();
    if (!useAIEstimate) {
      // Switching back to AI estimate — reset input to AI value
      setWeightStr(String(Math.round(baseGrams)));
    }
    setUseAIEstimate((v) => !v);
  };

  const switchUnit = (u: Unit) => {
    Haptics.selectionAsync();
    setUnit(u);
  };

  // Portion label for display (e.g. "150g" or "200ml")
  const portionLabel = useAIEstimate
    ? `${Math.round(baseGrams)}g (AI estimate)`
    : `${Math.round(currentAmount)}${unit}`;

  const logIt = async () => {
    if (!result) return;
    setSaving(true);
    try {
      // Always send grams to the backend (ml treated as 1:1 with g).
      const servingGrams = Math.round(effectiveGrams);
      await api("/food/log", {
        method: "POST",
        body: {
          food_name: result.food_name,
          calories: calcCalories,
          fat_g: calcFat,
          carbs_g: calcCarbs,
          protein_g: calcProtein,
          serving_size_g: servingGrams,
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

  // Quick-select chips relative to AI base serving
  const half = Math.round(baseGrams * 0.5);
  const full = Math.round(baseGrams);
  const oneHalf = Math.round(baseGrams * 1.5);
  const double = Math.round(baseGrams * 2);

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

        {analyzing ? (
          <View style={styles.loading}>
            <ActivityIndicator color={colors.brand} size="large" />
            <Text style={styles.loadingTxt}>
              {activeHint ? `Re-analyzing as "${activeHint}"…` : "Analyzing your food…"}
            </Text>
            <Text style={styles.loadingSub}>
              {activeHint ? "Re-calculating calories and macros" : "Estimating calories, fat, and carbs"}
            </Text>
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

        {result && !analyzing ? (
          <>
            {/* ── Result card ── */}
            <View style={styles.card}>
              <View style={styles.rowBetween}>
                <Text style={styles.foodName} testID="analysis-food-name">{result.food_name}</Text>
                <View style={[styles.verdict, { backgroundColor: verdictColor + "22" }]}>
                  <View style={[styles.dot, { backgroundColor: verdictColor }]} />
                  <Text style={[styles.verdictTxt, { color: verdictColor }]}>{verdictLabel}</Text>
                </View>
              </View>
              {result.reason ? <Text style={styles.reason}>{result.reason}</Text> : null}

              {/* ── Correction section ── */}
              <Pressable
                testID="btn-toggle-correction"
                onPress={() => setShowCorrection((v) => !v)}
                style={styles.correctToggleBtn}
              >
                <Ionicons
                  name={showCorrection ? "chevron-up" : "pencil-outline"}
                  size={15}
                  color={colors.brand}
                />
                <Text style={styles.correctToggleTxt}>
                  {showCorrection ? "Cancel" : "Wrong item? Tell AI to re-analyze"}
                </Text>
              </Pressable>

              {showCorrection && (
                <View style={styles.correctionBox}>
                  <Text style={styles.correctionLabel}>What food is in the photo?</Text>
                  <View style={styles.correctionInputRow}>
                    <TextInput
                      style={styles.correctionInput}
                      placeholder="e.g. Banana Shake, Almond Milk..."
                      placeholderTextColor={colors.muted}
                      value={correctionText}
                      onChangeText={setCorrectionText}
                      maxLength={120}
                      autoCapitalize="words"
                    />
                    <Pressable
                      style={[styles.reanalyzeBtn, !correctionText.trim() && styles.btnDisabled]}
                      disabled={!correctionText.trim() || analyzing}
                      onPress={() => {
                        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
                        runAnalysis(correctionText);
                      }}
                    >
                      <Text style={styles.reanalyzeBtnTxt}>Re-analyze</Text>
                    </Pressable>
                  </View>
                </View>
              )}


              <View style={styles.calorieBig}>
                <Text style={styles.calorieVal} testID="analysis-calories">{calcCalories}</Text>
                <Text style={styles.calorieUnit}>calories · {portionLabel}</Text>
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

            {/* ── Portion card ── */}
            <View style={styles.amountCard} testID="exact-amount-section">
              {/* Header row with toggle */}
              <View style={styles.amountHeader}>
                <Ionicons name="scale-outline" size={20} color={colors.brand} />
                <Text style={styles.amountTitle}>Portion Size</Text>
                <Pressable
                  testID="toggle-ai-estimate"
                  onPress={toggleEstimate}
                  style={styles.estimateToggle}
                >
                  <Ionicons
                    name={useAIEstimate ? "checkmark-circle" : "checkmark-circle-outline"}
                    size={16}
                    color={useAIEstimate ? colors.brand : colors.muted}
                  />
                  <Text style={[styles.estimateTxt, useAIEstimate && { color: colors.brand }]}>
                    Use AI estimate
                  </Text>
                </Pressable>
              </View>

              <Text style={styles.amountSubtitle}>
                {useAIEstimate
                  ? `Using AI's estimate of ${Math.round(baseGrams)}g — tap "Use AI estimate" to enter a custom amount.`
                  : "Enter your actual portion below for precise calories."}
              </Text>

              {/* Custom input — only visible when not using AI estimate */}
              {!useAIEstimate && (
                <>
                  {/* Unit picker */}
                  <View style={styles.unitRow}>
                    {UNITS.map((u) => (
                      <Pressable
                        key={u.value}
                        testID={`unit-${u.value}`}
                        onPress={() => switchUnit(u.value)}
                        style={[styles.unitChip, unit === u.value && styles.unitChipActive]}
                      >
                        <Text style={[styles.unitChipTxt, unit === u.value && styles.unitChipTxtActive]}>
                          {u.label}
                        </Text>
                      </Pressable>
                    ))}
                    <Text style={styles.unitHint}>
                      {unit === "ml" ? "For liquids (juice, milk, soup…)" : "For solids & semi-solids"}
                    </Text>
                  </View>

                  {/* Amount input */}
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
                    <Text style={styles.unitLabel}>{unit}</Text>
                  </View>

                  {/* Quick-select chips — always in grams equivalent */}
                  <View style={styles.chipsRow}>
                    {[
                      { label: "½ Serving", val: half },
                      { label: "1 Serving", val: full },
                      { label: "1.5×", val: oneHalf },
                      { label: "2×", val: double },
                    ].map((chip) => {
                      const isSelected = !useAIEstimate && Math.round(currentAmount) === chip.val;
                      return (
                        <Pressable
                          key={chip.label}
                          onPress={() => setQuickAmount(chip.val)}
                          style={[styles.chip, isSelected && styles.chipActive]}
                        >
                          <Text style={[styles.chipTxt, isSelected && styles.chipTxtActive]}>
                            {chip.label}
                          </Text>
                          <Text style={[styles.chipSub, isSelected && styles.chipTxtActive]}>
                            {chip.val}{unit}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </>
              )}
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
  // ── Result card
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
  calorieUnit: { fontSize: 12, color: colors.muted, textTransform: "uppercase", letterSpacing: 1.2, marginTop: 2 },
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
  // ── Portion card
  amountCard: {
    marginTop: spacing.md,
    padding: spacing.lg,
    backgroundColor: colors.surface2,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  amountHeader: { flexDirection: "row", alignItems: "center", gap: 8 },
  amountTitle: { fontSize: 16, fontWeight: "700", color: colors.onSurface, flex: 1 },
  estimateToggle: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  estimateTxt: { fontSize: 12, fontWeight: "700", color: colors.muted },
  amountSubtitle: { fontSize: 12, color: colors.muted, marginTop: spacing.sm, marginBottom: spacing.md, lineHeight: 18 },
  // Unit picker
  unitRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  unitChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  unitChipActive: {
    backgroundColor: colors.brandSoft,
    borderColor: colors.brand,
  },
  unitChipTxt: { fontSize: 14, fontWeight: "700", color: colors.muted },
  unitChipTxtActive: { color: colors.brand },
  unitHint: { fontSize: 11, color: colors.muted, flex: 1, flexWrap: "wrap" },
  // Amount input
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
    marginBottom: spacing.md,
  },
  weightInput: {
    fontSize: 28,
    fontWeight: "900",
    color: colors.onSurface,
    paddingVertical: 10,
    textAlign: "center",
    minWidth: 80,
  },
  unitLabel: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.muted,
    marginLeft: spacing.sm,
  },
  // Quick chips
  chipsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
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
  chipTxt: { fontSize: 12, fontWeight: "700", color: colors.muted },
  chipSub: { fontSize: 11, color: colors.muted, marginTop: 2 },
  chipTxtActive: { color: colors.brand },
  // Buttons
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

  // ── Correction section styles ──
  correctToggleBtn: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 6,
    paddingVertical: 6,
    paddingHorizontal: 10,
    backgroundColor: colors.brand + "18",
    borderRadius: radius.sm,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  correctToggleTxt: {
    fontSize: 13,
    fontWeight: "600",
    color: colors.brand,
  },
  correctionBox: {
    marginTop: spacing.xs,
    marginBottom: spacing.sm,
    padding: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  correctionLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.muted,
    marginBottom: spacing.xs,
  },
  correctionInputRow: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
  },
  correctionInput: {
    flex: 1,
    height: 42,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    fontSize: 14,
    color: colors.onSurface,
  },
  reanalyzeBtn: {
    backgroundColor: colors.brand,
    paddingHorizontal: 14,
    height: 42,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  reanalyzeBtnTxt: {
    color: colors.onBrand,
    fontSize: 13,
    fontWeight: "700",
  },
  btnDisabled: {
    opacity: 0.4,
  },

});
