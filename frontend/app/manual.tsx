import React, { useState, useRef, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  TextInput,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { colors, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
// Safe dynamic resolution of native modules to prevent crashes on older APKs
let AudioModule: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const av = require("expo-av");
  AudioModule = av?.Audio || null;
} catch (e) {
  AudioModule = null;
}

let FileSystemModule: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  FileSystemModule = require("expo-file-system");
} catch (e) {
  FileSystemModule = null;
}

export default function Manual() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [cal, setCal] = useState("");
  const [mealText, setMealText] = useState("");
  const [macros, setMacros] = useState<{
    protein_g: number;
    carbs_g: number;
    fat_g: number;
  } | null>(null);
  const [transcript, setTranscript] = useState("");
  const [recording, setRecording] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const recordingRef = useRef<any>(null);
  const maxTimerRef = useRef<any>(null);
  const silenceStartRef = useRef<number | null>(null);
  const isStoppingRef = useRef<boolean>(false);

  useEffect(() => {
    return () => {
      if (maxTimerRef.current) clearTimeout(maxTimerRef.current);
      if (recordingRef.current && AudioModule) {
        recordingRef.current.stopAndUnloadAsync().catch(() => {});
      }
    };
  }, []);

  // 1. Microphone recording powered by Sarvam AI with automatic stop
  const startRecording = async () => {
    try {
      setErr("");
      if (!AudioModule) {
        Alert.alert(
          "Voice Recording",
          "Voice input is compiling in your Google Play update. In the meantime, you can use 'Describe meal' below or enter details manually!",
          [{ text: "OK" }]
        );
        return;
      }

      isStoppingRef.current = false;
      silenceStartRef.current = null;
      if (maxTimerRef.current) clearTimeout(maxTimerRef.current);

      const perm = await AudioModule.requestPermissionsAsync();
      if (!perm.granted) {
        Alert.alert("Permission", "Microphone access is required to speak.");
        return;
      }

      await AudioModule.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const preset = AudioModule.RecordingOptionsPresets?.HIGH_QUALITY || {};
      const { recording } = await AudioModule.Recording.createAsync({
        ...preset,
        isMeteringEnabled: true,
      });

      // Silence detection: automatically stop recording when speech ends
      recording.setOnRecordingStatusUpdate((status: any) => {
        if (!status.isRecording || isStoppingRef.current) return;

        // Start checking for silence after 1.5 seconds of initial speech
        if (status.durationMillis > 1500) {
          const level = status.metering ?? -160;
          if (level < -42) {
            if (!silenceStartRef.current) {
              silenceStartRef.current = Date.now();
            } else if (Date.now() - silenceStartRef.current >= 1200) {
              stopRecording();
            }
          } else {
            silenceStartRef.current = null;
          }
        }
      });

      recordingRef.current = recording;
      setRecording(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

      // Max safety duration: auto-stop after 5 seconds
      maxTimerRef.current = setTimeout(() => {
        stopRecording();
      }, 5000);
    } catch (e: any) {
      console.warn("Recording start error:", e);
      setErr(e.message || "Could not start microphone.");
    }
  };

  const stopRecording = async () => {
    if (isStoppingRef.current) return;
    isStoppingRef.current = true;

    if (maxTimerRef.current) {
      clearTimeout(maxTimerRef.current);
      maxTimerRef.current = null;
    }
    silenceStartRef.current = null;

    try {
      const rec = recordingRef.current;
      if (!rec) {
        setRecording(false);
        isStoppingRef.current = false;
        return;
      }

      setRecording(false);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      await rec.stopAndUnloadAsync();

      const uri = rec.getURI();
      recordingRef.current = null;

      if (!uri) return;

      setAnalyzing(true);
      let b64 = "";

      if (Platform.OS === "web") {
        const response = await fetch(uri);
        const blob = await response.blob();
        b64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            const raw = reader.result as string;
            resolve(raw.includes(",") ? raw.split(",")[1] : raw);
          };
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });
      } else if (FileSystemModule?.readAsStringAsync) {
        b64 = await FileSystemModule.readAsStringAsync(uri, {
          encoding: "base64" as any,
        });
      }

      const data = await api("/food/voice-analyze", {
        method: "POST",
        body: { audio_base64: b64, language_code: "hi-IN" },
        auth: true,
      });

      if (data.food_name && data.food_name !== "Not food") {
        setName(data.food_name);
        setCal(String(data.calories || 0));
        setMacros({
          protein_g: data.protein_g || 0,
          carbs_g: data.carbs_g || 0,
          fat_g: data.fat_g || 0,
        });
        if (data.transcript) {
          setTranscript(data.transcript);
        }
      } else {
        setErr("Could not detect food in speech.");
      }
    } catch (e: any) {
      console.warn("Voice analysis error:", e);
      setErr(e.message || "Failed to analyze speech.");
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleRecording = () => {
    if (recording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  // 2. Text description analysis (fallback for typing meals in Hindi/English)
  const analyzeMealText = async () => {
    if (!mealText.trim()) return;
    setAnalyzing(true);
    setErr("");
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      const data = await api("/food/voice-analyze", {
        method: "POST",
        body: { text_input: mealText.trim(), language_code: "hi-IN" },
        auth: true,
      });

      if (data.food_name && data.food_name !== "Not food") {
        setName(data.food_name);
        setCal(String(data.calories || 0));
        setMacros({
          protein_g: data.protein_g || 0,
          carbs_g: data.carbs_g || 0,
          fat_g: data.fat_g || 0,
        });
        setTranscript(mealText.trim());
        setMealText("");
      } else {
        setErr("Could not detect food in text.");
      }
    } catch (e: any) {
      setErr(e.message || "Failed to analyze meal.");
    } finally {
      setAnalyzing(false);
    }
  };

  // 3. Submit meal to log
  const submit = async () => {
    if (!name.trim() || !cal.trim()) {
      setErr("Enter food name and calories");
      return;
    }
    const c = parseFloat(cal);
    if (Number.isNaN(c) || c < 0) {
      setErr("Enter valid calories");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      await api("/food/log", {
        method: "POST",
        body: {
          food_name: name.trim(),
          calories: c,
          source: transcript ? "voice" : "manual",
        },
      });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.replace("/(tabs)");
    } catch (e: any) {
      setErr(e.message || "Failed to save");
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={styles.wrap} edges={["top"]}>
      <View style={styles.header}>
        <Pressable testID="manual-close" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="close" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Add food</Text>
        <View style={{ width: 36 }} />
      </View>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          {/* Section: Speak */}
          <Text style={styles.sectionTitle}>Speak</Text>
          <Pressable
            testID="speak-toggle-btn"
            onPress={toggleRecording}
            disabled={analyzing}
            style={({ pressed }) => [
              styles.speakCard,
              recording && styles.speakCardActive,
              pressed && { opacity: 0.9 },
            ]}
          >
            {analyzing ? (
              <View style={styles.inlineRow}>
                <ActivityIndicator color={colors.brand} />
                <Text style={styles.analyzingTxt}>Analyzing speech...</Text>
              </View>
            ) : (
              <View style={styles.inlineRow}>
                <Ionicons
                  name={recording ? "mic" : "mic-outline"}
                  size={24}
                  color={recording ? colors.error : colors.brand}
                />
                <Text style={[styles.speakTxt, recording && styles.speakTxtActive]}>
                  {recording ? "Listening... (auto-stops)" : "Speak"}
                </Text>
              </View>
            )}
          </Pressable>

          {/* Text Description Box */}
          <View style={styles.textInputRow}>
            <TextInput
              style={styles.textInputFlex}
              placeholder="Describe meal"
              placeholderTextColor={colors.muted}
              value={mealText}
              onChangeText={setMealText}
            />
            <Pressable
              onPress={analyzeMealText}
              disabled={analyzing || !mealText.trim()}
              style={[
                styles.analyzeBtn,
                (!mealText.trim() || analyzing) && { opacity: 0.5 },
              ]}
            >
              <Text style={styles.analyzeBtnTxt}>Analyze</Text>
            </Pressable>
          </View>

          {transcript ? (
            <Text style={styles.transcript}>"{transcript}"</Text>
          ) : null}

          {/* Detected Meal Result Card */}
          {name && cal ? (
            <View style={styles.resultCard}>
              <View style={styles.resultHeader}>
                <View style={{ flex: 1, paddingRight: spacing.sm }}>
                  <Text style={styles.resultBadge}>AI ESTIMATE</Text>
                  <Text style={styles.resultFoodName}>{name}</Text>
                </View>
                <View style={styles.resultCalBadge}>
                  <Text style={styles.resultCalNumber}>{Math.round(parseFloat(cal))}</Text>
                  <Text style={styles.resultCalUnit}>kcal</Text>
                </View>
              </View>

              {macros ? (
                <View style={styles.macroRow}>
                  <View style={styles.macroPill}>
                    <Text style={styles.macroLabel}>Protein</Text>
                    <Text style={styles.macroVal}>{macros.protein_g}g</Text>
                  </View>
                  <View style={styles.macroPill}>
                    <Text style={styles.macroLabel}>Carbs</Text>
                    <Text style={styles.macroVal}>{macros.carbs_g}g</Text>
                  </View>
                  <View style={styles.macroPill}>
                    <Text style={styles.macroLabel}>Fat</Text>
                    <Text style={styles.macroVal}>{macros.fat_g}g</Text>
                  </View>
                </View>
              ) : null}

              <Pressable
                testID="manual-save-btn"
                onPress={submit}
                disabled={saving}
                style={({ pressed }) => [styles.btn, (pressed || saving) && { opacity: 0.85 }]}
              >
                {saving ? (
                  <ActivityIndicator color={colors.onBrand} />
                ) : (
                  <Text style={styles.btnTxt}>Add to log</Text>
                )}
              </Pressable>
            </View>
          ) : (
            <View style={styles.helperCard}>
              <Ionicons name="sparkles" size={24} color={colors.brand} />
              <Text style={styles.helperTitle}>Hands-free AI Logging</Text>
              <Text style={styles.helperSub}>
                Tap Speak or describe your meal. AI calculates calories & macros automatically.
              </Text>
            </View>
          )}

          {err ? (
            <Text style={styles.err} testID="manual-error">
              {err}
            </Text>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
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
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.onSurface,
    marginBottom: spacing.sm,
  },
  speakCard: {
    backgroundColor: colors.surface2,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  speakCardActive: {
    borderColor: colors.error,
    backgroundColor: "rgba(239, 68, 68, 0.08)",
  },
  inlineRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  speakTxt: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.brand,
  },
  speakTxtActive: {
    color: colors.error,
  },
  textInputRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  textInputFlex: {
    flex: 1,
    backgroundColor: colors.surface2,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    borderRadius: radius.md,
    fontSize: 14,
    color: colors.onSurface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  analyzeBtn: {
    backgroundColor: colors.brand,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  analyzeBtnTxt: {
    color: colors.onBrand,
    fontWeight: "700",
    fontSize: 13,
  },
  analyzingTxt: {
    fontSize: 14,
    color: colors.muted,
  },
  transcript: {
    fontSize: 13,
    color: colors.muted,
    fontStyle: "italic",
    marginTop: spacing.xs,
    paddingHorizontal: spacing.xs,
  },
  resultCard: {
    marginTop: spacing.xl,
    backgroundColor: colors.surface2,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  resultHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.md,
  },
  resultBadge: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.brand,
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  resultFoodName: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.onSurface,
  },
  resultCalBadge: {
    backgroundColor: colors.brandSoft,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.md,
    alignItems: "center",
    minWidth: 64,
  },
  resultCalNumber: {
    fontSize: 18,
    fontWeight: "800",
    color: colors.brand,
  },
  resultCalUnit: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.brand,
    marginTop: -2,
  },
  helperCard: {
    marginTop: spacing.xl,
    padding: spacing.xl,
    borderRadius: radius.lg,
    backgroundColor: colors.surface2,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  helperTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.onSurface,
    marginTop: spacing.sm,
  },
  helperSub: {
    fontSize: 13,
    color: colors.muted,
    textAlign: "center",
    marginTop: 4,
    lineHeight: 18,
  },
  label: {
    fontSize: 13,
    color: colors.onSurface2,
    marginTop: spacing.md,
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
  macroRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  macroPill: {
    flex: 1,
    backgroundColor: colors.surface2,
    paddingVertical: spacing.xs,
    borderRadius: radius.sm,
    alignItems: "center",
  },
  macroLabel: {
    fontSize: 11,
    color: colors.muted,
  },
  macroVal: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.onSurface,
    marginTop: 2,
  },
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
