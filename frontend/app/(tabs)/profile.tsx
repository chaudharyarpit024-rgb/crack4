import { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  TextInput,
  ActivityIndicator,
  Switch,
} from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { clearToken } from "@/src/api";
import { StreakData } from "@/src/streak";
import {
  isReminderEnabled,
  scheduleStreakReminder,
  cancelStreakReminder,
} from "@/src/notifications";


const GOALS = [
  { key: "lose", label: "Lose" },
  { key: "maintain", label: "Maintain" },
  { key: "gain", label: "Gain" },
];

export default function Profile() {
  const router = useRouter();
  const [me, setMe] = useState<any>(null);
  const [days, setDays] = useState<any[]>([]);
  const [streak, setStreak] = useState<StreakData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reminderOn, setReminderOn] = useState(true);
  const [reminderUpdating, setReminderUpdating] = useState(false);

  const [goal, setGoal] = useState<string>("");
  const [weight, setWeight] = useState("");
  const [height, setHeight] = useState("");

  const load = useCallback(async () => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const [u, h, s] = await Promise.all([
        api<any>("/auth/me"),
        api<{ days: any[] }>("/food/history?days=30"),
        api<StreakData>(`/food/streak?timezone=${encodeURIComponent(tz || "")}`).catch(() => null),
      ]);
      setMe(u);
      setGoal(u.goal || "");
      setWeight(u.weight_kg ? String(u.weight_kg) : "");
      setHeight(u.height_cm ? String(u.height_cm) : "");
      setDays(h.days);
      setStreak(s);
      const enabled = await isReminderEnabled();
      setReminderOn(enabled);
    } catch {
      router.replace("/login");
    } finally {
      setLoading(false);
    }
  }, [router]);


  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const save = async () => {
    setSaving(true);
    try {
      const u = await api<any>("/profile", {
        method: "PUT",
        body: {
          goal: goal || undefined,
          weight_kg: weight ? parseFloat(weight) : undefined,
          height_cm: height ? parseFloat(height) : undefined,
        },
      });
      setMe(u);
    } catch {}
    setSaving(false);
  };

  const toggleReminder = async (val: boolean) => {
    const prev = reminderOn;
    setReminderOn(val);
    setReminderUpdating(true);
    try {
      if (val) {
        await scheduleStreakReminder();
      } else {
        await cancelStreakReminder();
      }
    } catch {
      try {
        const persisted = await isReminderEnabled();
        setReminderOn(persisted);
      } catch {
        setReminderOn(prev);
      }
    } finally {
      setReminderUpdating(false);
    }
  };

  const logout = async () => {
    await clearToken();
    router.replace("/login");
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.wrap}>
        <ActivityIndicator color={colors.brand} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.wrap} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.headerRow}>
          <Text style={styles.title}>Profile</Text>
          <Pressable testID="logout-btn" onPress={logout} style={styles.logout}>
            <Ionicons name="log-out-outline" size={18} color={colors.muted} />
          </Pressable>
        </View>

        <View style={styles.card}>
          <View style={styles.avatar}>
            <Text style={styles.avatarTxt}>
              {(me?.name || me?.email || "?")[0].toUpperCase()}
            </Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.name}>{me?.name}</Text>
            <Text style={styles.email}>{me?.email}</Text>
            {me?.daily_target ? (
              <Text style={styles.target}>Daily target: {me.daily_target} kcal</Text>
            ) : null}
          </View>
        </View>

        <View style={styles.streakStatsRow} testID="profile-streak-stats">
          <View style={styles.streakStatBox}>
            <View style={styles.streakStatHeader}>
              <Text style={styles.streakStatEmoji}>🔥</Text>
              <Text style={styles.streakStatLabel}>Current Streak</Text>
            </View>
            <Text style={styles.streakStatValue} testID="profile-current-streak">
              {streak?.current_streak ?? 0} <Text style={styles.streakStatUnit}>days</Text>
            </Text>
          </View>

          <View style={styles.streakStatBox}>
            <View style={styles.streakStatHeader}>
              <Ionicons name="trophy" size={16} color="#D97706" />
              <Text style={styles.streakStatLabel}>Best Streak</Text>
            </View>
            <Text style={styles.streakStatValue} testID="profile-best-streak">
              {streak?.longest_streak ?? 0} <Text style={styles.streakStatUnit}>days</Text>
            </Text>
          </View>
        </View>

        <Text style={styles.section}>Update your goal</Text>

        <View style={styles.goalRow}>
          {GOALS.map((g) => (
            <Pressable
              key={g.key}
              testID={`profile-goal-${g.key}`}
              onPress={() => setGoal(g.key)}
              style={[styles.goalChip, goal === g.key && styles.goalChipActive]}
            >
              <Text
                style={[
                  styles.goalChipTxt,
                  goal === g.key && { color: colors.brand, fontWeight: "700" },
                ]}
              >
                {g.label}
              </Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.row}>
          <View style={{ flex: 1, marginRight: spacing.sm }}>
            <Text style={styles.label}>Weight (kg)</Text>
            <TextInput
              testID="profile-weight-input"
              style={styles.input}
              keyboardType="numeric"
              value={weight}
              onChangeText={setWeight}
            />
          </View>
          <View style={{ flex: 1, marginLeft: spacing.sm }}>
            <Text style={styles.label}>Height (cm)</Text>
            <TextInput
              testID="profile-height-input"
              style={styles.input}
              keyboardType="numeric"
              value={height}
              onChangeText={setHeight}
            />
          </View>
        </View>

        <Pressable
          testID="profile-save-btn"
          onPress={save}
          disabled={saving}
          style={({ pressed }) => [styles.btn, (pressed || saving) && { opacity: 0.85 }]}
        >
          {saving ? (
            <ActivityIndicator color={colors.onBrand} />
          ) : (
            <Text style={styles.btnTxt}>Save changes</Text>
          )}
        </Pressable>

        <Pressable
          testID="manage-subscription"
          onPress={() => router.push("/subscribe")}
          style={styles.subRow}
        >
          <Ionicons name="star" size={18} color={colors.brand} />
          <Text style={styles.subRowTxt}>Manage subscription</Text>
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </Pressable>

        <View style={styles.reminderRow} testID="reminder-toggle-row">
          <View style={styles.reminderLeft}>
            <Ionicons name="notifications-outline" size={18} color={colors.brand} />
            <Text style={styles.reminderTxt}>Daily streak reminder</Text>
          </View>
          <Switch
            testID="reminder-switch"
            value={reminderOn}
            disabled={reminderUpdating}
            onValueChange={toggleReminder}
            trackColor={{ false: colors.surface3, true: colors.brandSoft }}
            thumbColor={reminderOn ? colors.brand : colors.muted}
          />
        </View>

        <View style={styles.legalRow}>
          <Pressable
            testID="link-terms"
            onPress={() => router.push("/terms")}
            style={styles.legalItem}
          >
            <Ionicons name="document-text-outline" size={16} color={colors.muted} />
            <Text style={styles.legalTxt}>Terms of Service</Text>
          </Pressable>
          <View style={styles.legalDivider} />
          <Pressable
            testID="link-privacy"
            onPress={() => router.push("/privacy")}
            style={styles.legalItem}
          >
            <Ionicons name="shield-checkmark-outline" size={16} color={colors.muted} />
            <Text style={styles.legalTxt}>Privacy Policy</Text>
          </Pressable>
        </View>

        <Text style={styles.section}>Last 30 days</Text>
        {days.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyTxt}>No history yet</Text>
          </View>
        ) : (
          days.map((d) => {
            const target = me?.daily_target || 2000;
            let s: "deficit" | "good" | "over" = "good";
            if (d.total_calories < target * 0.7) s = "deficit";
            else if (d.total_calories > target * 1.1) s = "over";
            const color = s === "good" ? colors.success : s === "over" ? colors.error : colors.warning;
            return (
              <View key={d.date} style={styles.dayRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.dayDate}>{d.date}</Text>
                  <Text style={styles.dayMeals}>{d.count} meals</Text>
                </View>
                <Text style={styles.dayCal}>{Math.round(d.total_calories)} kcal</Text>
                <View style={[styles.dot, { backgroundColor: color }]} />
              </View>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.surface },
  scroll: { padding: spacing.xl, paddingBottom: spacing.xxxl },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  title: { fontSize: 28, fontWeight: "800", color: colors.onSurface },
  logout: { padding: 8 },
  card: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.lg,
    backgroundColor: colors.surface2,
    borderRadius: radius.lg,
    marginTop: spacing.lg,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  avatarTxt: { color: colors.onBrand, fontWeight: "800", fontSize: 22 },
  name: { fontSize: 16, fontWeight: "700", color: colors.onSurface },
  email: { fontSize: 13, color: colors.muted, marginTop: 2 },
  target: { fontSize: 12, color: colors.brand, marginTop: 4, fontWeight: "600" },
  section: {
    marginTop: spacing.xl,
    fontSize: 13,
    color: colors.muted,
    textTransform: "uppercase",
    fontWeight: "700",
    letterSpacing: 1.5,
    marginBottom: spacing.md,
  },
  goalRow: { flexDirection: "row", gap: spacing.sm },
  goalChip: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: radius.pill,
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  goalChipActive: { borderColor: colors.brand, backgroundColor: colors.brandSoft },
  goalChipTxt: { color: colors.onSurface2 },
  row: { flexDirection: "row", marginTop: spacing.md },
  label: { fontSize: 13, color: colors.onSurface2, marginBottom: spacing.xs, fontWeight: "600" },
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
  btn: {
    backgroundColor: colors.brand,
    paddingVertical: 14,
    borderRadius: radius.md,
    alignItems: "center",
    marginTop: spacing.lg,
  },
  btnTxt: { color: colors.onBrand, fontSize: 16, fontWeight: "700" },
  subRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.lg,
    backgroundColor: colors.brandSoft,
    borderRadius: radius.md,
    marginTop: spacing.xl,
    gap: spacing.md,
  },
  subRowTxt: { flex: 1, color: colors.brand, fontWeight: "700", fontSize: 15 },
  reminderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: spacing.lg,
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
    marginTop: spacing.sm,
  },
  reminderLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  reminderTxt: { color: colors.onSurface2, fontWeight: "600", fontSize: 15 },
  legalRow: {
    flexDirection: "row",
    marginTop: spacing.md,
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
    padding: spacing.sm,
  },
  legalItem: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.sm,
    gap: 6,
  },
  legalDivider: { width: 1, backgroundColor: colors.border, marginVertical: 4 },
  legalTxt: { fontSize: 13, color: colors.onSurface2, fontWeight: "600" },
  empty: { padding: spacing.xl, backgroundColor: colors.surface2, borderRadius: radius.lg, alignItems: "center" },
  emptyTxt: { color: colors.muted },
  dayRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.md,
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
    marginBottom: spacing.sm,
  },
  dayDate: { fontSize: 14, fontWeight: "600", color: colors.onSurface },
  dayMeals: { fontSize: 12, color: colors.muted, marginTop: 2 },
  dayCal: { fontSize: 14, fontWeight: "700", color: colors.brand, marginRight: spacing.sm },
  dot: { width: 10, height: 10, borderRadius: 5 },
  streakStatsRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.md,
  },
  streakStatBox: {
    flex: 1,
    backgroundColor: "#FFF8F5",
    borderWidth: 1.5,
    borderColor: "#FDD8CE",
    borderRadius: radius.md,
    padding: spacing.md,
  },
  streakStatHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 4,
  },
  streakStatEmoji: {
    fontSize: 16,
  },
  streakStatLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.muted,
  },
  streakStatValue: {
    fontSize: 20,
    fontWeight: "800",
    color: colors.onSurface,
  },
  streakStatUnit: {
    fontSize: 12,
    fontWeight: "500",
    color: colors.muted,
  },
});

