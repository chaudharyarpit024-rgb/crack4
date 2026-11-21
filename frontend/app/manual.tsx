import React, { useState, useRef } from "react";
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
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";

export default function Manual() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [cal, setCal] = useState("");
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

  const recordingRef = useRef<Audio.Recording | null>(null);

  // 1. Microphone recording powered by Sarvam AI
  const startRecording = async () => {
    try {
      setErr("");
      const perm = await Audio.requestPermissionsAsync();
      if (!perm.granted) {
        Alert.alert("Permission", "Microphone access is required to speak.");
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
    } catch (e: any) {
      console.warn("Recording start error:", e);
      setErr(e.message || "Could not start microphone.");
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

      if (!uri) return;

      setAnalyzing(true);
      const b64 = await FileSystem.readAsStringAsync(uri, {
        encoding: FileSystem.EncodingType.Base64,
      });

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

  // 2. Submit meal to log
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
                  name={recording ? "stop-circle" : "mic"}
                  size={24}
                  color={recording ? colors.error : colors.brand}
                />
                <Text style={[styles.speakTxt, recording && styles.speakTxtActive]}>
                  {recording ? "Stop recording" : "Speak"}
                </Text>
              </View>
            )}
          </Pressable>

          {transcript ? (
            <Text style={styles.transcript}>"{transcript}"</Text>
          ) : null}

          {/* Section: Manual */}
          <Text style={[styles.sectionTitle, { marginTop: spacing.xl }]}>Manual</Text>

          <Text style={styles.label}>Food name</Text>
          <TextInput
            testID="manual-name-input"
            style={styles.input}
            placeholder="Food name"
            placeholderTextColor={colors.muted}
            value={name}
            onChangeText={setName}
          />

          <Text style={styles.label}>Calories</Text>
          <TextInput
            testID="manual-cal-input"
            style={styles.input}
            placeholder="Calories"
            placeholderTextColor={colors.muted}
            keyboardType="numeric"
            value={cal}
            onChangeText={setCal}
          />

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

          {err ? (
            <Text style={styles.err} testID="manual-error">
              {err}
            </Text>
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
