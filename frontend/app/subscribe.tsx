import { useCallback, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  ScrollView,
  Linking,
  Platform,
} from "react-native";
import { useRouter, useLocalSearchParams, useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, radius } from "@/src/theme";
import { api, API_BASE } from "@/src/api";


type Sub = {
  status: string;
  active: boolean;
  trial_active: boolean;
  paid_active: boolean;
  trial_ends_at?: string | null;
  days_left: number;
  amount_paise: number;
  currency: string;
  rzp_configured: boolean;
};

export default function Subscribe() {
  const router = useRouter();
  const params = useLocalSearchParams<{ reason?: string }>();
  const [sub, setSub] = useState<Sub | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      const s = await api<Sub>("/subscription/me");
      setSub(s);
    } catch (e: any) {
      setErr(e.message || "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const startCheckout = async () => {
    setBusy(true);
    setErr("");
    try {
      const res = await api<{ subscription_id: string }>("/subscription/checkout", {
        method: "POST",
      });
      const url = `${API_BASE}/api/subscription/checkout-page?subscription_id=${encodeURIComponent(res.subscription_id)}`;
      // Open in system browser (works in Expo Go). Real native build can use WebView.
      await Linking.openURL(url);
    } catch (e: any) {
      setErr(e.message || "Could not start checkout");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.wrap}>
        <ActivityIndicator color={colors.brand} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  const priceRupees = ((sub?.amount_paise ?? 5700) / 100).toFixed(0);
  const reasonLine =
    params.reason === "trial-ended"
      ? "Your free trial has ended. Subscribe to keep AI food scanning."
      : params.reason === "trial-limit"
      ? "You've used all 5 free scans for today. Subscribe for 500 scans/month."
      : sub?.paid_active
        ? "You're on the Premium plan."
        : sub?.trial_active
          ? `You have ${sub.days_left} day${sub.days_left === 1 ? "" : "s"} left in your free trial.`
          : "Unlock AI food scanning with premium.";

  return (
    <SafeAreaView style={styles.wrap} edges={["top"]}>
      <View style={styles.header}>
        <Pressable testID="sub-close" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="close" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Premium</Text>
        <View style={{ width: 36 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.heroBadge}>
          <Ionicons name="star" size={16} color={colors.brand} />
          <Text style={styles.heroBadgeTxt}>CRACK PREMIUM</Text>
        </View>

        <Text style={styles.title}>Track smarter.{"\n"}Snap. Scan. Log.</Text>
        <Text style={styles.sub}>{reasonLine}</Text>

        <View style={styles.priceCard} testID="price-card">
          <View style={styles.priceRow}>
            <Text style={styles.priceCurrency}>₹</Text>
            <Text style={styles.priceVal}>{priceRupees}</Text>
            <Text style={styles.priceUnit}>/month</Text>
          </View>
          <View style={styles.trialTag}>
            <Ionicons name="gift" size={14} color={colors.brand} />
            <Text style={styles.trialTagTxt}>10-day free trial</Text>
          </View>
          <Text style={styles.priceSub}>UPI Autopay · cancel anytime</Text>
        </View>

        <View style={styles.features}>
          {[
            { i: "camera" as const, t: "AI food scan", s: "Snap a photo, get calories in seconds" },
            { i: "sparkles" as const, t: "Monthly 500 clicks", s: "Snap & analyze up to 500 meals per month" },
            { i: "flame" as const, t: "Smart calorie coach", s: "Deficit / on-track / over alerts" },
            { i: "trending-up" as const, t: "30-day history", s: "See progress against your goal" },
          ].map((f) => (
            <View key={f.t} style={styles.feature}>
              <View style={styles.featIcon}>
                <Ionicons name={f.i} size={18} color={colors.brand} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.featT}>{f.t}</Text>
                <Text style={styles.featS}>{f.s}</Text>
              </View>
            </View>
          ))}
        </View>

        {err ? (
          <Text style={styles.err} testID="sub-error">{err}</Text>
        ) : null}

        {sub?.paid_active ? (
          <View style={styles.activeCard}>
            <Ionicons name="checkmark-circle" size={22} color={colors.success} />
            <Text style={styles.activeTxt}>Subscription active</Text>
          </View>
        ) : (
          <Pressable
            testID="start-checkout-btn"
            onPress={startCheckout}
            disabled={busy}
            style={({ pressed }) => [styles.cta, (pressed || busy) && { opacity: 0.85 }]}
          >
            {busy ? (
              <ActivityIndicator color={colors.onBrand} />
            ) : (
              <>
                <Ionicons name="lock-open" size={18} color={colors.onBrand} />
                <Text style={styles.ctaTxt}>
                  {sub?.trial_active ? "Continue with premium" : "Start 10-day free trial"}
                </Text>
              </>
            )}
          </Pressable>
        )}

        <View style={styles.paymentsBox} testID="payment-options">
          <Text style={styles.paymentsTitle}>Accepted payment methods</Text>
          <View style={styles.paymentsRow}>
            <View style={styles.paymentChip}>
              <Ionicons name="phone-portrait" size={14} color={colors.brand} />
              <Text style={styles.paymentChipTxt}>UPI Autopay</Text>
            </View>
            <View style={styles.paymentChip}>
              <Ionicons name="card" size={14} color={colors.brand} />
              <Text style={styles.paymentChipTxt}>Debit / Credit</Text>
            </View>
            <View style={styles.paymentChip}>
              <Ionicons name="business" size={14} color={colors.brand} />
              <Text style={styles.paymentChipTxt}>Net Banking</Text>
            </View>
            <View style={styles.paymentChip}>
              <Ionicons name="wallet" size={14} color={colors.brand} />
              <Text style={styles.paymentChipTxt}>Wallets</Text>
            </View>
          </View>
          <Text style={styles.paymentsFoot}>
            Payments are securely processed by Razorpay. You can cancel your subscription anytime from
            Profile → Manage subscription.
          </Text>
        </View>

        <View style={styles.legalLinks}>
          <Pressable testID="sub-terms" onPress={() => router.push("/terms")}>
            <Text style={styles.legalLinkTxt}>Terms of Service</Text>
          </Pressable>
          <Text style={styles.legalSep}>·</Text>
          <Pressable testID="sub-privacy" onPress={() => router.push("/privacy")}>
            <Text style={styles.legalLinkTxt}>Privacy Policy</Text>
          </Pressable>
        </View>

        {!sub?.rzp_configured ? (
          <Text style={styles.note} testID="rzp-note">
            Payment gateway not yet configured. Ask the admin to add Razorpay keys in{" "}
            <Text style={{ fontWeight: "700" }}>backend/.env</Text> to enable real billing.
          </Text>
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
  scroll: { padding: spacing.xl, paddingBottom: spacing.xxxl },
  heroBadge: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.brandSoft,
    gap: 6,
  },
  heroBadgeTxt: { color: colors.brand, fontSize: 11, fontWeight: "800", letterSpacing: 1.2 },
  title: {
    marginTop: spacing.md,
    fontSize: 30,
    fontWeight: "900",
    color: colors.onSurface,
    lineHeight: 36,
  },
  sub: { marginTop: spacing.sm, fontSize: 14, color: colors.muted, lineHeight: 20 },
  priceCard: {
    marginTop: spacing.xl,
    padding: spacing.xl,
    backgroundColor: colors.brandSoft,
    borderRadius: radius.lg,
    alignItems: "center",
  },
  priceRow: { flexDirection: "row", alignItems: "flex-end" },
  priceCurrency: { fontSize: 22, fontWeight: "800", color: colors.brand, marginBottom: 8 },
  priceVal: { fontSize: 56, fontWeight: "900", color: colors.brand, lineHeight: 60 },
  priceUnit: { fontSize: 16, color: colors.brand, marginLeft: 4, marginBottom: 10, fontWeight: "700" },
  trialTag: {
    marginTop: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.pill,
    gap: 6,
  },
  trialTagTxt: { color: colors.brand, fontSize: 12, fontWeight: "700" },
  priceSub: { marginTop: spacing.sm, fontSize: 12, color: colors.brandDark },
  features: { marginTop: spacing.xl },
  feature: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacing.md,
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
    marginBottom: spacing.sm,
  },
  featIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.brandSoft,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  featT: { fontSize: 15, fontWeight: "700", color: colors.onSurface },
  featS: { fontSize: 12, color: colors.muted, marginTop: 2 },
  cta: {
    flexDirection: "row",
    backgroundColor: colors.brand,
    paddingVertical: 16,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xl,
    gap: 8,
  },
  ctaTxt: { color: colors.onBrand, fontSize: 16, fontWeight: "700" },
  activeCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#DCFCE7",
    padding: spacing.lg,
    borderRadius: radius.md,
    marginTop: spacing.xl,
    gap: 8,
  },
  activeTxt: { color: colors.success, fontWeight: "800", fontSize: 15 },
  err: { color: colors.error, marginTop: spacing.md, fontSize: 13 },
  paymentsBox: {
    marginTop: spacing.xl,
    padding: spacing.lg,
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
  },
  paymentsTitle: {
    fontSize: 12,
    color: colors.muted,
    textTransform: "uppercase",
    fontWeight: "700",
    letterSpacing: 1.5,
    marginBottom: spacing.sm,
  },
  paymentsRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  paymentChip: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: colors.surface,
    borderRadius: radius.pill,
    gap: 6,
  },
  paymentChipTxt: { fontSize: 12, color: colors.onSurface2, fontWeight: "600" },
  paymentsFoot: { marginTop: spacing.md, fontSize: 12, color: colors.muted, lineHeight: 18 },
  legalLinks: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.lg,
    gap: 8,
  },
  legalLinkTxt: { fontSize: 13, color: colors.muted, textDecorationLine: "underline" },
  legalSep: { color: colors.muted },
  note: {
    marginTop: spacing.lg,
    fontSize: 12,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 18,
  },
});
