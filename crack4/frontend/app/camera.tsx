  import { useRef, useState } from "react";
  import { View, Text, StyleSheet, Pressable, ActivityIndicator, Platform } from "react-native";
  import { useRouter } from "expo-router";
  import { CameraView, useCameraPermissions } from "expo-camera";
  import * as ImageManipulator from "expo-image-manipulator";
  import * as ImagePicker from "expo-image-picker";
  import * as Haptics from "expo-haptics";
  import { Ionicons } from "@expo/vector-icons";
  import { SafeAreaView } from "react-native-safe-area-context";
  import { colors, spacing, radius } from "@/src/theme";

  export default function CameraScreen() {
    const router = useRouter();
    const [perm, requestPerm] = useCameraPermissions();
    const camRef = useRef<CameraView | null>(null);
    const [busy, setBusy] = useState(false);
    const [facing, setFacing] = useState<"back" | "front">("back");
    const [flash, setFlash] = useState<"off" | "on" | "auto">("off");

    const goAnalyze = async (uri: string) => {
      const manipulated = await ImageManipulator.manipulateAsync(
        uri,
        [{ resize: { width: 800 } }],
        { compress: 0.6, format: ImageManipulator.SaveFormat.JPEG, base64: true }
      );
      router.replace({ pathname: "/analyze", params: { b64: manipulated.base64 as string } });
    };

    const capture = async () => {
      if (busy || !camRef.current) return;
      setBusy(true);
      try {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        const photo: any = await camRef.current.takePictureAsync({
          quality: 0.5,
          base64: false,
          skipProcessing: true,
        });
        if (!photo?.uri) throw new Error("Capture failed");
        await goAnalyze(photo.uri);
      } catch {
        setBusy(false);
      }
    };

    const cycleFlash = () => {
      if (busy) return;
      Haptics.selectionAsync();
      setFlash((f) => (f === "off" ? "on" : f === "on" ? "auto" : "off"));
    };

    const pickGallery = async () => {
      if (busy) return;
      try {
        const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (!perm.granted) return;
        const res = await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
          quality: 0.6,
          allowsEditing: false,
        });
        if (res.canceled || !res.assets?.[0]?.uri) return;
        setBusy(true);
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        await goAnalyze(res.assets[0].uri);
      } catch {
        setBusy(false);
      }
    };

    if (!perm) return <View style={{ flex: 1, backgroundColor: "#000" }} />;
    if (!perm.granted) {
      return (
        <SafeAreaView style={styles.permWrap}>
          <Ionicons name="camera-outline" size={64} color={colors.brand} />
          <Text style={styles.permTitle}>Camera access needed</Text>
          <Text style={styles.permSub}>To scan food and estimate calories</Text>
          <Pressable testID="grant-cam" onPress={requestPerm} style={styles.btn}>
            <Text style={styles.btnTxt}>Grant permission</Text>
          </Pressable>
          <Pressable testID="pick-gallery-noperm" onPress={pickGallery} style={styles.btnGhost}>
            <Text style={styles.btnGhostTxt}>Or pick from gallery</Text>
          </Pressable>
          <Pressable onPress={() => router.back()} style={{ marginTop: spacing.lg }}>
            <Text style={{ color: colors.muted }}>Cancel</Text>
          </Pressable>
        </SafeAreaView>
      );
    }

    return (
      <View style={styles.wrap}>
        <CameraView
          ref={camRef}
          style={StyleSheet.absoluteFill}
          facing={facing}
          flash={flash}
          enableTorch={flash === "on"}
        />

        <SafeAreaView style={styles.overlay} edges={["top", "bottom"]}>
          <View style={styles.topBar}>
            <Pressable testID="cam-close" onPress={() => router.back()} style={styles.iconBtn}>
              <Ionicons name="close" size={24} color="#fff" />
            </Pressable>
            <View style={styles.topCenter}>
              <Text style={styles.topTitle}>Scan food</Text>
              {flash === "auto" && (
                <View style={styles.autoPill}>
                  <Text style={styles.autoPillTxt}>AUTO FLASH</Text>
                </View>
              )}
            </View>
            <Pressable
              testID="cam-flip"
              onPress={() => setFacing((f) => (f === "back" ? "front" : "back"))}
              style={styles.iconBtn}
            >
              <Ionicons name="camera-reverse" size={24} color="#fff" />
            </Pressable>
          </View>

          <View style={styles.frameWrap}>
            <View style={styles.frame} />
            <Text style={styles.hint}>Center the food inside the frame</Text>
          </View>

          <View style={styles.bottomBar}>
            <Pressable
              testID="pick-gallery-btn"
              onPress={pickGallery}
              disabled={busy}
              style={[styles.sideBtn, busy && { opacity: 0.5 }]}
            >
              <Ionicons name="images" size={22} color="#fff" />
              <Text style={styles.sideTxt}>Gallery</Text>
            </Pressable>

            <Pressable
              testID="shutter-btn"
              onPress={capture}
              disabled={busy}
              style={[styles.shutter, busy && { opacity: 0.6 }]}
            >
              {busy ? (
                <ActivityIndicator color={colors.brand} />
              ) : (
                <View style={styles.shutterInner} />
              )}
            </Pressable>

            <Pressable
              testID="flash-btn"
              onPress={cycleFlash}
              disabled={busy}
              style={[styles.sideBtn, busy && { opacity: 0.5 }]}
            >
              <Ionicons
                name={flash === "on" ? "flash" : flash === "auto" ? "flash-outline" : "flash-off"}
                size={22}
                color={flash === "off" ? "#fff" : colors.brand}
              />
              <Text
                style={[
                  styles.sideTxt,
                  flash !== "off" && { color: colors.brand },
                ]}
              >
                {flash === "on" ? "On" : flash === "auto" ? "Auto" : "Off"}
              </Text>
            </Pressable>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  const styles = StyleSheet.create({
    wrap: { flex: 1, backgroundColor: "#000" },
    overlay: { flex: 1, justifyContent: "space-between" },
    topBar: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: spacing.lg,
      paddingTop: spacing.md,
    },
    topCenter: { alignItems: "center" },
    autoPill: {
      marginTop: 4,
      paddingHorizontal: 8,
      paddingVertical: 2,
      borderRadius: radius.pill,
      backgroundColor: colors.brand,
    },
    autoPillTxt: { color: colors.onBrand, fontSize: 10, fontWeight: "800" },
    iconBtn: {
      width: 40,
      height: 40,
      borderRadius: 20,
      backgroundColor: "rgba(0,0,0,0.4)",
      alignItems: "center",
      justifyContent: "center",
    },
    topTitle: { color: "#fff", fontSize: 15, fontWeight: "700" },
    frameWrap: { alignItems: "center" },
    frame: {
      width: 280,
      height: 280,
      borderWidth: 3,
      borderColor: colors.brand,
      borderRadius: radius.lg,
      backgroundColor: "transparent",
    },
    hint: {
      color: "#fff",
      marginTop: spacing.md,
      fontSize: 13,
      backgroundColor: "rgba(0,0,0,0.4)",
      paddingHorizontal: 12,
      paddingVertical: 6,
      borderRadius: radius.pill,
    },
    bottomBar: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: spacing.xl,
      paddingBottom: spacing.xl,
    },
    sideBtn: {
      alignItems: "center",
      justifyContent: "center",
      width: 72,
    },
    sideTxt: { color: "#fff", fontSize: 11, marginTop: 4, fontWeight: "600" },
    shutter: {
      width: 80,
      height: 80,
      borderRadius: 40,
      borderWidth: 5,
      borderColor: "#fff",
      backgroundColor: "rgba(255,255,255,0.15)",
      alignItems: "center",
      justifyContent: "center",
    },
    shutterInner: {
      width: 60,
      height: 60,
      borderRadius: 30,
      backgroundColor: colors.brand,
    },
    permWrap: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      padding: spacing.xl,
      backgroundColor: colors.surface,
    },
    permTitle: { fontSize: 20, fontWeight: "800", color: colors.onSurface, marginTop: spacing.lg },
    permSub: { fontSize: 14, color: colors.muted, marginTop: spacing.xs, marginBottom: spacing.xl },
    btn: {
      backgroundColor: colors.brand,
      paddingVertical: 14,
      paddingHorizontal: spacing.xl,
      borderRadius: radius.md,
    },
    btnTxt: { color: colors.onBrand, fontSize: 16, fontWeight: "700" },
    btnGhost: { marginTop: spacing.md, paddingVertical: 12, paddingHorizontal: spacing.lg },
    btnGhostTxt: { color: colors.brand, fontSize: 14, fontWeight: "700" },
  });