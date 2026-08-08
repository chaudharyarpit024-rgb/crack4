import { View, Text, StyleSheet, ScrollView, Pressable } from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, radius } from "@/src/theme";

const SECTIONS: { h: string; b: string }[] = [
  {
    h: "Overview",
    b: "This Privacy Policy explains what data the CRACK app collects, how it is used, and your choices. By using the App you agree to this Policy.",
  },
  {
    h: "Data We Collect",
    b: "Account: email, name, hashed password. Health inputs: goal (gain/lose/maintain), weight, height, age, gender. Meal logs: food name, calories, protein, fat, carbs, timestamp, and optionally the meal photo you upload. Subscription: your Razorpay subscription ID and status (we never see your card or UPI PIN).",
  },
  {
    h: "How We Use Your Data",
    b: "• Provide core features (calorie tracking, history, daily target).\n• Send meal photos to Google Gemini for AI analysis; photos are transmitted only for the duration of that analysis request.\n• Process payments and manage your subscription via Razorpay.\n• Improve reliability (aggregate, non‑identifying diagnostics).",
  },
  {
    h: "Legal Basis",
    b: "We process personal data to perform our contract with you (providing the service), for our legitimate interests (security, fraud prevention), and where required by law.",
  },
  {
    h: "Third Parties",
    b: "• Google Gemini — receives your uploaded meal photo and returns a nutrition estimate.\n• Razorpay — processes subscription payments and stores payment credentials in accordance with PCI‑DSS.\n• Cloud hosting / MongoDB — stores your account and meal data at rest.\nWe do not sell your personal data.",
  },
  {
    h: "Data Retention",
    b: "We keep your account and meal logs until you delete your account. Uploaded meal photos are not retained after analysis unless you explicitly attach one to a saved log.",
  },
  {
    h: "Security",
    b: "Passwords are stored hashed with bcrypt. Auth tokens are stored on‑device in the secure keychain (iOS) or encrypted storage (Android). All API traffic uses HTTPS.",
  },
  {
    h: "Your Rights",
    b: "You can access, correct, export, or delete your data. To delete your account, log in and use the Profile screen or email support@crackapp.example. We will respond within a reasonable time and as required by applicable law.",
  },
  {
    h: "Children",
    b: "CRACK is not directed at children under 13 (or the equivalent minimum age in your country). If we learn we collected data from a child under that age, we will delete it.",
  },
  {
    h: "Changes",
    b: "We may update this Policy. Material changes will be highlighted in the app or by email.",
  },
  {
    h: "Contact",
    b: "Privacy questions: privacy@crackapp.example.",
  },
];

export default function Privacy() {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.wrap} edges={["top"]}>
      <View style={styles.header}>
        <Pressable testID="privacy-close" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="arrow-back" size={20} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Privacy Policy</Text>
        <View style={{ width: 36 }} />
      </View>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.updated}>Last updated: February 2026</Text>
        {SECTIONS.map((s) => (
          <View key={s.h} style={styles.section}>
            <Text style={styles.h}>{s.h}</Text>
            <Text style={styles.b}>{s.b}</Text>
          </View>
        ))}
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
  updated: { color: colors.muted, fontSize: 12, marginBottom: spacing.lg },
  section: { marginBottom: spacing.lg },
  h: { fontSize: 15, fontWeight: "800", color: colors.onSurface, marginBottom: 6 },
  b: { fontSize: 14, color: colors.onSurface2, lineHeight: 21 },
});
