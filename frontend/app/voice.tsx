import React, { useState, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  ScrollView,
  TextInput,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { colors, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";

interface VoiceResult {
  food_name: string;
  transcript: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  serving_size_g?: number;
  verdict: "good" | "bad" | "ok";
  reason: string;
}

export default function VoiceScreen() {
  const router = useRouter();
  const [recording, setRecording] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [typedText, setTypedText] = useState("");
  const [result, setResult] = useState<VoiceResult | null>(null);

  const recordingRef = useRef<Audio.Recording | null>(null);

  // 1. Send real audio soundwaves to Sarvam AI STT via backend
  const analyzeAudio = async (base64Audio: string) => {
    setAnalyzing(true);
    setResult(null);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      const data = await api("/food/voice-analyze", {
        method: "POST",
        body: { audio_base64: base64Audio, language_code: "hi-IN" },
        auth: true,
      });

      if (data.food_name === "Not food" || data.calories === 0) {
        Alert.alert(
          "No Food Detected",
          "We could not detect any food in your speech. Please mention food or drinks (e.g. '2 roti aur moong dal')."
        );
      } else {
        setResult(data);
      }
    } catch (err: any) {
      Alert.alert("Sarvam AI Error", err.message || "Failed to transcribe audio.");
    } finally {
      setAnalyzing(false);
    }
  };

  // 2. Analyze typed/dictated text input
  const analyzeInput = async (spokenText: string) => {
    if (!spokenText.trim()) return;
    setAnalyzing(true);
    setResult(null);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      const data = await api("/food/voice-analyze", {
        method: "POST",
        body: { text_input: spokenText.trim(), language_code: "hi-IN" },
        auth: true,
      });

      if (data.food_name === "Not food" || data.calories === 0) {
        Alert.alert(
          "No Food Detected",
          "We could not detect any food in your speech. Please describe a meal or drink (e.g. '2 roti aur dal')."
        );
      } else {
        setResult(data);
      }
    } catch (err: any) {
      Alert.alert("Analysis Error", err.message || "Failed to analyze speech.");
    } finally {
      setAnalyzing(false);
    }
  };

  // 3. Real Audio Recording with expo-av (Native mobile & Web)
  const startRecording = async () => {
    try {
      const perm = await Audio.requestPermissionsAsync();
      if (!perm.granted) {
        Alert.alert("Permission Needed", "Please grant microphone permission to record audio.");
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recordingRef.current = recording;
      setRecording(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } catch (err: any) {
      console.warn("Recording start error:", err);
      Alert.alert("Recording Error", err.message || "Could not start audio recording.");
    }
  };

  const stopRecording = async () => {
    try {
      const rec = recordingRef.current;
      if (!rec) return;

      setRecording(false);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      await rec.stopAndUnloadAsync();

      const uri = rec.getURI();
      recordingRef.current = null;

      if (!uri) {
        Alert.alert("Error", "No audio recording captured.");
        return;
      }

      const b64 = await FileSystem.readAsStringAsync(uri, {
        encoding: FileSystem.EncodingType.Base64,
      });

      await analyzeAudio(b64);
    } catch (err: any) {
      console.warn("Recording stop error:", err);
      Alert.alert("Error", err.message || "Failed to process audio recording.");
    }
  };

  const toggleListening = () => {
    if (recording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  // Confirm and log to MongoDB
  const logMeal = async () => {
    if (!result) return;
    setSaving(true);
    try {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      await api("/food/log", {
        method: "POST",
        body: {
          food_name: result.food_name,
          calories: Math.round(result.calories),
          protein_g: Math.round(result.protein_g * 10) / 10,
          carbs_g: Math.round(result.carbs_g * 10) / 10,
          fat_g: Math.round(result.fat_g * 10) / 10,
          serving_size_g: result.serving_size_g || 150,
          source: "ai",
        },
        auth: true,
      });
      router.replace("/(tabs)");
    } catch (err: any) {
      Alert.alert("Save Failed", err.message || "Failed to log meal.");
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="close" size={24} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Voice Meal Logger</Text>
        <View style={styles.sarvamBadge}>
          <Text style={styles.sarvamBadgeText}>Sarvam AI</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Main Microphone Section */}
        <View style={styles.micSection}>
          <Pressable
            style={[styles.micButton, recording && styles.micButtonRecording]}
            onPress={toggleListening}
            disabled={analyzing}
          >
            <Ionicons
              name={recording ? "stop" : "mic"}
              size={48}
              color={colors.onBrand}
            />
          </Pressable>

          <Text style={styles.statusTitle}>
            {recording
              ? "Recording voice... Tap to Stop"
              : analyzing
              ? "Transcribing with Sarvam AI..."
              : "Tap to record in Hindi or English"}
          </Text>
          <Text style={styles.statusSub}>
            Speak naturally: "Maine do aloo parathe dahi ke saath khaye"
          </Text>
        </View>

        {analyzing && (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color={colors.brand} />
            <Text style={styles.loadingTxt}>Sarvam AI is transcribing Indian audio & calculating macros...</Text>
          </View>
        )}

        {/* Quick Test Chips for Evaluators */}
        {!result && !analyzing && (
          <View style={styles.sampleSection}>
            <Text style={styles.sampleLabel}>Or tap a sample to test:</Text>
            <View style={styles.chipRow}>
              {[
                "2 roti aur 1 katori moong dal",
                "2 aloo parathe with dahi",
                "Ek plate rajma chawal",
              ].map((phrase) => (
                <Pressable
                  key={phrase}
                  style={styles.chip}
                  onPress={() => {
                    setTypedText(phrase);
                    analyzeInput(phrase);
                  }}
                >
                  <Text style={styles.chipText}>{phrase}</Text>
                </Pressable>
              ))}
            </View>

            {/* Manual text input / keyboard dictation */}
            <View style={styles.textInputWrap}>
              <TextInput
                style={styles.input}
                placeholder="Or type/speak Hindi/English meal..."
                placeholderTextColor={colors.muted}
                value={typedText}
                onChangeText={setTypedText}
                onSubmitEditing={() => analyzeInput(typedText)}
              />
              <Pressable
                style={styles.sendBtn}
                onPress={() => analyzeInput(typedText)}
              >
                <Ionicons name="arrow-forward" size={20} color={colors.onBrand} />
              </Pressable>
            </View>
          </View>
        )}

        {/* Recognized Meal Result Card */}
        {result && !analyzing && (
          <View style={styles.resultCard}>
            <View style={styles.transcriptWrap}>
              <Text style={styles.transcriptLabel}>Heard (Sarvam STT):</Text>
              <Text style={styles.transcriptText}>"{result.transcript}"</Text>
            </View>

            <View style={styles.divider} />

            <View style={styles.foodTitleRow}>
              <Text style={styles.foodTitle}>{result.food_name}</Text>
              <View
                style={[
                  styles.verdictBadge,
                  result.verdict === "good"
                    ? styles.verdictGood
                    : styles.verdictOk,
                ]}
              >
                <Text style={styles.verdictText}>
                  {result.verdict.toUpperCase()}
                </Text>
              </View>
            </View>

            {result.reason ? (
              <Text style={styles.reasonText}>{result.reason}</Text>
            ) : null}

            {/* Big Calories Display */}
            <View style={styles.calRow}>
              <Text style={styles.calNumber}>{Math.round(result.calories)}</Text>
              <Text style={styles.calUnit}>kcal</Text>
            </View>

            {/* Macros Breakdown */}
            <View style={styles.macrosRow}>
              <View style={styles.macroCol}>
                <Text style={styles.macroVal}>
                  {Math.round(result.protein_g)}g
                </Text>
                <Text style={styles.macroLabel}>Protein</Text>
              </View>
              <View style={styles.macroCol}>
                <Text style={styles.macroVal}>{Math.round(result.carbs_g)}g</Text>
                <Text style={styles.macroLabel}>Carbs</Text>
              </View>
              <View style={styles.macroCol}>
                <Text style={styles.macroVal}>{Math.round(result.fat_g)}g</Text>
                <Text style={styles.macroLabel}>Fat</Text>
              </View>
            </View>

            {/* Action Buttons */}
            <Pressable
              style={[styles.logBtn, saving && styles.btnDisabled]}
              onPress={logMeal}
              disabled={saving}
            >
              {saving ? (
                <ActivityIndicator color={colors.onBrand} />
              ) : (
                <Text style={styles.logBtnText}>Add to Today's Food Log</Text>
              )}
            </Pressable>

            <Pressable
              style={styles.retryBtn}
              onPress={() => {
                setResult(null);
                setTypedText("");
              }}
            >
              <Text style={styles.retryText}>Record another meal</Text>
            </Pressable>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.surface2 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backBtn: { padding: spacing.xs },
  headerTitle: { fontSize: 17, fontWeight: "700", color: colors.onSurface },
  sarvamBadge: {
    backgroundColor: "#F3E8FF",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radius.pill,
  },
  sarvamBadgeText: { fontSize: 11, fontWeight: "800", color: "#7E22CE" },
  content: { padding: spacing.lg, alignItems: "center" },
  micSection: { alignItems: "center", marginVertical: spacing.xl },
  micButton: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: colors.brand,
    justifyContent: "center",
    alignItems: "center",
    elevation: 6,
    shadowColor: colors.brand,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 10,
    marginBottom: spacing.md,
  },
  micButtonRecording: {
    backgroundColor: colors.error,
    transform: [{ scale: 1.08 }],
  },
  statusTitle: { fontSize: 18, fontWeight: "800", color: colors.onSurface, marginBottom: 4 },
  statusSub: { fontSize: 13, color: colors.muted, textAlign: "center", paddingHorizontal: spacing.lg },
  loadingWrap: { alignItems: "center", marginVertical: spacing.lg },
  loadingTxt: { fontSize: 13, color: colors.muted, marginTop: spacing.sm, textAlign: "center" },
  sampleSection: { width: "100%", marginTop: spacing.md },
  sampleLabel: { fontSize: 13, fontWeight: "600", color: colors.muted, marginBottom: spacing.sm },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: spacing.lg },
  chip: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: radius.pill,
  },
  chipText: { fontSize: 12, color: colors.onSurface, fontWeight: "600" },
  textInputWrap: { flexDirection: "row", gap: 8, width: "100%" },
  input: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 14,
    color: colors.onSurface,
  },
  sendBtn: {
    backgroundColor: colors.brand,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    justifyContent: "center",
    alignItems: "center",
  },
  resultCard: {
    width: "100%",
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.xl,
    borderWidth: 1,
    borderColor: colors.border,
    marginTop: spacing.sm,
  },
  transcriptWrap: { backgroundColor: colors.surface2, padding: spacing.md, borderRadius: radius.md },
  transcriptLabel: { fontSize: 11, fontWeight: "700", color: colors.muted, textTransform: "uppercase" },
  transcriptText: { fontSize: 14, color: colors.onSurface, fontStyle: "italic", marginTop: 2 },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: spacing.md },
  foodTitleRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  foodTitle: { fontSize: 18, fontWeight: "800", color: colors.onSurface, flex: 1 },
  verdictBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: radius.sm },
  verdictGood: { backgroundColor: "#DCFCE7" },
  verdictOk: { backgroundColor: "#FEF3C7" },
  verdictText: { fontSize: 11, fontWeight: "800", color: colors.onSurface },
  reasonText: { fontSize: 12, color: colors.muted, marginTop: 4, lineHeight: 18 },
  calRow: { flexDirection: "row", alignItems: "baseline", marginVertical: spacing.md },
  calNumber: { fontSize: 36, fontWeight: "900", color: colors.brand },
  calUnit: { fontSize: 16, fontWeight: "700", color: colors.muted, marginLeft: 6 },
  macrosRow: { flexDirection: "row", justifyContent: "space-around", marginVertical: spacing.md },
  macroCol: { alignItems: "center" },
  macroVal: { fontSize: 16, fontWeight: "800", color: colors.onSurface },
  macroLabel: { fontSize: 12, color: colors.muted, marginTop: 2 },
  logBtn: {
    backgroundColor: colors.brand,
    borderRadius: radius.md,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: spacing.md,
  },
  btnDisabled: { opacity: 0.6 },
  logBtnText: { color: colors.onBrand, fontSize: 15, fontWeight: "700" },
  retryBtn: { alignItems: "center", paddingVertical: spacing.md, marginTop: spacing.xs },
  retryText: { fontSize: 13, color: colors.muted, fontWeight: "600" },
});

