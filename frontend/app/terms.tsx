import { View, Text, StyleSheet, ScrollView, Pressable } from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, radius } from "@/src/theme";

const SECTIONS: { h: string; b: string }[] = [
  {
    h: "1. Acceptance of Terms",
    b: "By creating an account or using the CRACK mobile application (the “App”), you agree to these Terms of Service. If you do not agree, do not use the App.",
  },
  {
    h: "2. The Service",
    b: "CRACK is a personal diet tracker. You can log meals manually or capture a photo of your food; the App sends the photo to a third‑party AI provider (Google Gemini) to estimate calories, protein, fat, and carbohydrates. Estimates are approximate and are not medical advice.",
  },
  {
    h: "3. Not Medical Advice",
    b: "CRACK is intended for general wellness tracking. It is not a medical device and does not provide medical, nutritional, or dietary advice. Always consult a qualified professional before making health, diet, or exercise decisions, especially if you have any medical condition.",
  },
  {
    h: "4. Accounts",
    b: "You are responsible for keeping your password secure and for all activity under your account. You must be at least 13 years old (or the minimum age for digital consent in your country) to use CRACK.",
  },
  {
    h: "5. Subscription & Billing",
    b: "New accounts receive a complimentary free trial of Premium features (AI food scan) as indicated in the app at registration. After the trial, Premium is billed at ₹57 per month via Razorpay UPI Autopay (or supported card mandates). You may cancel anytime; access continues until the end of the paid period. Prices, features, and terms are subject to change with notice.",
  },
  {
    h: "6. Payments & Refunds",
    b: "Payments are processed by Razorpay Software Pvt. Ltd. and are subject to Razorpay’s terms and privacy policy. Except where required by law, subscription fees are non‑refundable once a billing cycle has started.",
  },
  {
    h: "7. Acceptable Use",
    b: "You agree not to reverse‑engineer, scrape, resell, or misuse the App or its AI features. Do not upload content that is unlawful, harmful, or infringes anyone’s rights.",
  },
  {
    h: "8. User Content",
    b: "You retain ownership of the meal photos and data you submit. You grant CRACK a limited license to process them solely to provide the service (including sending them to the AI provider for analysis).",
  },
  {
    h: "9. Third‑Party Services",
    b: "CRACK uses Google Gemini (AI analysis), Razorpay (payments), and MongoDB Atlas / cloud hosting (data storage). Your use of these features is also subject to their respective terms.",
  },
  {
    h: "10. Disclaimers & Limitation of Liability",
    b: "The App is provided “as is” without warranties of any kind. To the maximum extent permitted by law, CRACK and its operators are not liable for any indirect, incidental, or consequential damages arising from your use of the App.",
  },
  {
    h: "11. Termination",
    b: "We may suspend or terminate your account for violations of these Terms. You may delete your account anytime from the Profile screen or by contacting support.",
  },
  {
    h: "12. Changes",
    b: "We may update these Terms from time to time. Continued use of the App after changes means you accept the updated Terms.",
  },
  {
    h: "13. Contact",
    b: "Questions? Email support@crackapp.example.",
  },
];

export default function Terms() {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.wrap} edges={["top"]}>
      <View style={styles.header}>
        <Pressable testID="terms-close" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="arrow-back" size={20} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Terms of Service</Text>
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
