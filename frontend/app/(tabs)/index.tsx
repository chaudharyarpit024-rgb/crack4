import { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { colors, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { isNetworkError, isAuthError } from "@/src/utils/network";

import { User } from "@/src/auth";
import { StreakCard } from "@/src/components/StreakCard";
import { StreakData } from "@/src/streak";


type LogItem = {
  id: string;
  food_name: string;
  calories: number;
  protein_g?: number;
  timestamp: string;
  source: string;
};

type Sub = {
  active: boolean;
  trial_active: boolean;
  paid_active: boolean;
  days_left: number;
  status: string;
};

function StatusBadge({ status }: { status: "deficit" | "good" | "over" }) {
  const map = {
    deficit: { bg: "#FEF3C7", fg: colors.warning, label: "Under target" },
    good: { bg: "#DCFCE7", fg: colors.success, label: "On track" },
    over: { bg: "#FEE2E2", fg: colors.error, label: "Overeaten" },
  } as const;
  const s = map[status];
  return (
    <View style={[styles.badge, { backgroundColor: s.bg }]} testID={`status-${status}`}>
      <Text style={[styles.badgeTxt, { color: s.fg }]}>{s.label}</Text>
    </View>
  );
}

function CalorieRing({ eaten, target }: { eaten: number; target: number }) {
  const pct = Math.min(100, Math.round((eaten / target) * 100 || 0));
  return (
    <View style={styles.ring} testID="calorie-ring">
      <Text style={styles.ringPct}>{pct}%</Text>
      <Text style={styles.ringVal}>
        {Math.round(eaten)} <Text style={styles.ringSub}>/ {target}</Text>
      </Text>
      <Text style={styles.ringLabel}>calories</Text>
      <View style={styles.ringBar}>
        <View style={[styles.ringFill, { width: `${pct}%` }]} />
      </View>
    </View>
  );
}

export default function Home() {
  const router = useRouter();
  const [me, setMe] = useState<User | null>(null);
  const [items, setItems] = useState<LogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [protein, setProtein] = useState(0);
  const [sub, setSub] = useState<Sub | null>(null);
  const [streak, setStreak] = useState<StreakData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const [u, t, s, streakRes] = await Promise.all([
        api<User>("/auth/me"),
        api<{ items: LogItem[]; total_calories: number; total_protein_g: number }>("/food/today"),
        api<Sub>("/subscription/me"),
        api<StreakData>(`/food/streak?timezone=${encodeURIComponent(tz || "")}`).catch(() => null),
      ]);
      setMe(u);
      setItems(t.items);
      setTotal(t.total_calories);
      setProtein(t.total_protein_g || 0);
      setSub(s);
      setStreak(streakRes);
    } catch (e: any) {
      if (isNetworkError(e)) {
        router.replace("/network-error");
      } else if (isAuthError(e)) {
        router.replace("/session-expired");
      } else if (e?.status && e.status >= 500) {
        router.replace("/server-error");
      } else {
        router.replace("/login");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [router]);


  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const target = me?.daily_target || 2000;
  let status: "deficit" | "good" | "over" = "good";
  if (total < target * 0.7) status = "deficit";
  else if (total > target * 1.1) status = "over";

  const del = async (id: string) => {
    try {
      await api(`/food/${id}`, { method: "DELETE" });
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      load();
    } catch {}
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
      <View style={styles.header}>
        <View>
          <Text style={styles.hello}>Hi, {me?.name || "there"}</Text>
          <Text style={styles.brand}>CRACK</Text>
        </View>
        <Pressable
          testID="profile-icon"
          onPress={() => router.push("/(tabs)/profile")}
          style={styles.avatar}
        >
          <Ionicons name="person" size={20} color={colors.brand} />
        </Pressable>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
      >
        {sub && (sub.trial_active || !sub.paid_active) ? (
          <Pressable
            testID="trial-banner"
            onPress={() => router.push("/subscribe")}
            style={styles.trialBanner}
          >
            <Ionicons
              name={sub.trial_active ? "gift" : "lock-closed"}
              size={16}
              color={colors.brand}
            />
            <Text style={styles.trialTxt}>
              {sub.trial_active
                ? `Free trial · ${sub.days_left} day${sub.days_left === 1 ? "" : "s"} left`
                : "Trial ended · Subscribe to unlock AI scan"}
            </Text>
            <Ionicons name="chevron-forward" size={16} color={colors.brand} />
          </Pressable>
        ) : null}

        <CalorieRing eaten={total} target={target} />
        <View style={styles.macroPillRow} testID="today-macros">
          <View style={styles.macroPill}>
            <Ionicons name="fitness" size={14} color={colors.brand} />
            <Text style={styles.macroPillLabel}>Protein</Text>
            <Text style={styles.macroPillVal} testID="today-protein">{Math.round(protein)}g</Text>
          </View>
          <View style={{ alignItems: "center" }}>
            <StatusBadge status={status} />
          </View>
        </View>

        <StreakCard data={streak} />

        <View style={styles.section}>

          <Text style={styles.sectionTitle}>You ate today</Text>
          {items.length === 0 ? (
            <View style={styles.empty}>
              <Ionicons name="restaurant-outline" size={40} color={colors.muted} />
              <Text style={styles.emptyTxt}>No food logged yet</Text>
              <Text style={styles.emptySub}>Tap the button below to add your first meal</Text>
            </View>
          ) : (
            items.map((it) => (
              <View key={it.id} style={styles.logRow} testID={`log-row-${it.id}`}>
                <View style={styles.logIcon}>
                  <Ionicons
                    name={it.source === "ai" ? "camera" : "create"}
                    size={16}
                    color={colors.brand}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.logName} numberOfLines={1}>{it.food_name}</Text>
                  <View style={styles.logMetaRow}>
                    <Text style={styles.logTime}>
                      {new Date(it.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </Text>
                    {it.protein_g ? (
                      <>
                        <Text style={styles.logDot}>·</Text>
                        <Text style={styles.logProtein} testID={`log-protein-${it.id}`}>
                          {Math.round(it.protein_g)}g protein
                        </Text>
                      </>
                    ) : null}
                  </View>
                </View>
                <Text style={styles.logCal}>{Math.round(it.calories)} kcal</Text>
                <Pressable testID={`delete-${it.id}`} onPress={() => del(it.id)} style={styles.del}>
                  <Ionicons name="close" size={16} color={colors.muted} />
                </Pressable>
              </View>
            ))
          )}
        </View>

        <View style={{ height: 120 }} />
      </ScrollView>

      <View style={styles.fabWrap} pointerEvents="box-none">
        <Pressable
          testID="manual-fab"
          onPress={() => {
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
            router.push("/manual");
          }}
          style={styles.fabSecondary}
        >
          <Ionicons name="create-outline" size={22} color={colors.brand} />
          <Text style={styles.fabSecondaryTxt}>Manual</Text>
        </Pressable>
        <Pressable
          testID="camera-fab"
          onPress={() => {
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
            if (sub && !sub.active) {
              router.push({ pathname: "/subscribe", params: { reason: "trial-ended" } });
            } else {
              router.push("/camera");
            }
          }}
          style={styles.fabPrimary}
        >
          <Ionicons name="camera" size={26} color={colors.onBrand} />
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
  },
  hello: { fontSize: 13, color: colors.muted },
  brand: { fontSize: 22, fontWeight: "900", color: colors.brand, letterSpacing: 2 },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.brandSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  scroll: { paddingHorizontal: spacing.xl, paddingBottom: spacing.xxxl },
  ring: {
    marginTop: spacing.md,
    alignItems: "center",
    padding: spacing.xl,
    backgroundColor: colors.surface2,
    borderRadius: radius.lg,
  },
  ringPct: { fontSize: 14, color: colors.brand, fontWeight: "700", letterSpacing: 1 },
  ringVal: { fontSize: 40, fontWeight: "900", color: colors.onSurface, marginTop: 4 },
  ringSub: { fontSize: 18, color: colors.muted, fontWeight: "600" },
  ringLabel: { fontSize: 12, color: colors.muted, textTransform: "uppercase", letterSpacing: 2, marginTop: 2 },
  ringBar: {
    marginTop: spacing.lg,
    height: 10,
    width: "100%",
    backgroundColor: colors.surface3,
    borderRadius: radius.pill,
    overflow: "hidden",
  },
  ringFill: { height: "100%", backgroundColor: colors.brand, borderRadius: radius.pill },
  macroPillRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.md,
  },
  macroPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface2,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: radius.pill,
    gap: 6,
  },
  macroPillLabel: { fontSize: 12, color: colors.muted, fontWeight: "600" },
  macroPillVal: { fontSize: 14, color: colors.onSurface, fontWeight: "800" },
  badge: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: radius.pill },
  badgeTxt: { fontSize: 12, fontWeight: "700", letterSpacing: 0.5 },
  section: { marginTop: spacing.xl },
  sectionTitle: {
    fontSize: 13,
    color: colors.muted,
    textTransform: "uppercase",
    fontWeight: "700",
    letterSpacing: 1.5,
    marginBottom: spacing.md,
  },
  empty: {
    alignItems: "center",
    padding: spacing.xl,
    backgroundColor: colors.surface2,
    borderRadius: radius.lg,
  },
  emptyTxt: { marginTop: spacing.sm, fontSize: 15, color: colors.onSurface2, fontWeight: "600" },
  emptySub: { fontSize: 12, color: colors.muted, marginTop: 4, textAlign: "center" },
  logRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.md,
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
    marginBottom: spacing.sm,
  },
  logIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.brandSoft,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  logName: { fontSize: 15, fontWeight: "600", color: colors.onSurface },
  logMetaRow: { flexDirection: "row", alignItems: "center", marginTop: 2 },
  logTime: { fontSize: 12, color: colors.muted },
  logDot: { fontSize: 12, color: colors.muted, marginHorizontal: 6 },
  logProtein: { fontSize: 12, color: colors.brand, fontWeight: "600" },
  logCal: { fontSize: 14, fontWeight: "700", color: colors.brand, marginRight: spacing.sm },
  del: { padding: 4 },
  fabWrap: {
    position: "absolute",
    right: spacing.lg,
    bottom: 84,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  fabSecondary: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.lg,
    paddingVertical: 12,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: "#000",
    shadowOpacity: 0.08,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  fabSecondaryTxt: { color: colors.brand, fontWeight: "700", marginLeft: 6 },
  trialBanner: {
    marginTop: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.brandSoft,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    borderRadius: radius.pill,
    gap: 8,
    marginBottom: spacing.sm,
  },
  trialTxt: { flex: 1, color: colors.brand, fontWeight: "700", fontSize: 13 },
  fabPrimary: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: colors.brand,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.brand,
    shadowOpacity: 0.35,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
});
