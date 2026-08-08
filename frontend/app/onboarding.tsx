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

const GOALS: { key: "lose" | "maintain" | "gain"; label: string; sub: string }[] = [
  { key: "lose", label: "Lose weight", sub: "Calorie deficit" },
  { key: "maintain", label: "Maintain", sub: "Stay balanced" },
  { key: "gain", label: "Gain weight", sub: "Calorie surplus" },
];

export default function Onboarding() {
  const router = useRouter();
  const [goal, setGoal] = useState<"lose" | "maintain" | "gain" | null>(null);
  const [weight, setWeight] = useState("");
  const [height, setHeight] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState<"male" | "female" | "other" | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!goal || !weight || !height) {
      setErr("Please fill goal, weight and height");
      return;
    }
    setLoading(true);
    setErr("");
    try {
      await api("/profile", {
        method: "PUT",
        body: {
          goal,
          weight_kg: parseFloat(weight),
          height_cm: parseFloat(height),
          age: age ? parseInt(age) : undefined,
          gender: gender || undefined,
        },
      });
      router.replace("/(tabs)");
    } catch (e: any) {
      setErr(e.message || "Failed to save");
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
          <Text style={styles.h1}>Set your goal</Text>
          <Text style={styles.sub}>We'll estimate your daily calorie need</Text>

          {GOALS.map((g) => (
            <Pressable
              key={g.key}
              testID={`goal-${g.key}`}
              onPress={() => setGoal(g.key)}
              style={[styles.goalCard, goal === g.key && styles.goalActive]}
            >
              <View>
                <Text style={[styles.goalLabel, goal === g.key && { color: colors.brand }]}>
                  {g.label}
                </Text>
                <Text style={styles.goalSub}>{g.sub}</Text>
              </View>
              <View style={[styles.radio, goal === g.key && styles.radioActive]} />
            </Pressable>
          ))}

          <View style={styles.row}>
            <View style={{ flex: 1, marginRight: spacing.sm }}>
              <Text style={styles.label}>Weight (kg)</Text>
              <TextInput
                testID="onb-weight-input"
                style={styles.input}
                keyboardType="numeric"
                placeholder="70"
                placeholderTextColor={colors.muted}
                value={weight}
                onChangeText={setWeight}
              />
            </View>
            <View style={{ flex: 1, marginLeft: spacing.sm }}>
              <Text style={styles.label}>Height (cm)</Text>
              <TextInput
                testID="onb-height-input"
                style={styles.input}
                keyboardType="numeric"
                placeholder="175"
                placeholderTextColor={colors.muted}
                value={height}
                onChangeText={setHeight}
              />
            </View>
          </View>

          <View style={styles.row}>
            <View style={{ flex: 1, marginRight: spacing.sm }}>
              <Text style={styles.label}>Age (optional)</Text>
              <TextInput
                testID="onb-age-input"
                style={styles.input}
                keyboardType="numeric"
                placeholder="25"
                placeholderTextColor={colors.muted}
                value={age}
                onChangeText={setAge}
              />
            </View>
            <View style={{ flex: 1, marginLeft: spacing.sm }}>
              <Text style={styles.label}>Gender</Text>
              <View style={styles.genderRow}>
                {(["male", "female", "other"] as const).map((g) => (
                  <Pressable
                    key={g}
                    testID={`gender-${g}`}
                    onPress={() => setGender(g)}
                    style={[styles.chip, gender === g && styles.chipActive]}
                  >
                    <Text
                      style={[styles.chipTxt, gender === g && { color: colors.brand, fontWeight: "700" }]}
                    >
                      {g[0].toUpperCase() + g.slice(1)}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>
          </View>

          {err ? (
            <Text style={styles.err} testID="onb-error">
              {err}
            </Text>
          ) : null}

          <Pressable
            testID="onb-continue-btn"
            onPress={submit}
            disabled={loading}
            style={({ pressed }) => [styles.btn, (pressed || loading) && { opacity: 0.85 }]}
          >
            {loading ? (
              <ActivityIndicator color={colors.onBrand} />
            ) : (
              <Text style={styles.btnTxt}>Continue</Text>
            )}
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.surface },
  scroll: { padding: spacing.xl, paddingBottom: spacing.xxxl },
  h1: { fontSize: 28, fontWeight: "800", color: colors.onSurface },
  sub: { fontSize: 14, color: colors.muted, marginTop: spacing.xs, marginBottom: spacing.xl },
  goalCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: colors.surface2,
    borderWidth: 2,
    borderColor: "transparent",
    marginBottom: spacing.md,
  },
  goalActive: { borderColor: colors.brand, backgroundColor: colors.brandSoft },
  goalLabel: { fontSize: 16, fontWeight: "700", color: colors.onSurface },
  goalSub: { fontSize: 13, color: colors.muted, marginTop: 2 },
  radio: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.borderStrong || colors.border,
  },
  radioActive: { borderColor: colors.brand, backgroundColor: colors.brand },
  row: { flexDirection: "row", marginTop: spacing.md },
  label: {
    fontSize: 13,
    color: colors.onSurface2,
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
  genderRow: { flexDirection: "row" },
  chip: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: radius.pill,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    marginRight: 6,
  },
  chipActive: { borderColor: colors.brand, backgroundColor: colors.brandSoft },
  chipTxt: { fontSize: 13, color: colors.onSurface2 },
  btn: {
    backgroundColor: colors.brand,
    paddingVertical: 16,
    borderRadius: radius.md,
    alignItems: "center",
    marginTop: spacing.xl,
  },
  btnTxt: { color: colors.onBrand, fontSize: 16, fontWeight: "700" },
  err: { color: colors.error, marginTop: spacing.md, fontSize: 13 },
});
