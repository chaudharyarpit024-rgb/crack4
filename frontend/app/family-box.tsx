import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Share,
} from "react-native";
import { useRouter, useFocusEffect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { colors, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";

interface LeaderboardMember {
  user_id: string;
  name: string;
  goal: string;
  calories_consumed: number;
  daily_target: number;
  target_percentage: number;
  score: number;
  rank: number;
  is_me: boolean;
}

interface FamilyBox {
  id: string;
  name: string;
  invite_code: string;
  creator_id: string;
  member_count: number;
}

export default function FamilyBoxScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [box, setBox] = useState<FamilyBox | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardMember[]>([]);

  // Form states for non-members
  const [mode, setMode] = useState<"create" | "join">("create");
  const [boxName, setBoxName] = useState("");
  const [inviteCode, setInviteCode] = useState("");

  const fetchBoxData = useCallback(async () => {
    try {
      const res = await api("/family-box/my-box", { auth: true });
      setBox(res.box || null);
      setLeaderboard(res.leaderboard || []);
    } catch (err: any) {
      console.warn("Failed to load family box", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchBoxData();
    }, [fetchBoxData])
  );

  const onRefresh = () => {
    setRefreshing(true);
    fetchBoxData();
  };

  const handleCreateBox = async () => {
    if (!boxName.trim()) {
      Alert.alert("Missing Name", "Please enter a name for your Family Box.");
      return;
    }
    setSubmitting(true);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      await api("/family-box/create", {
        method: "POST",
        body: { name: boxName.trim() },
        auth: true,
      });
      setBoxName("");
      await fetchBoxData();
    } catch (err: any) {
      Alert.alert("Creation Failed", err.message || "Could not create family box.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleJoinBox = async () => {
    if (!inviteCode.trim()) {
      Alert.alert("Missing Code", "Please enter the invite code.");
      return;
    }
    setSubmitting(true);
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      await api("/family-box/join", {
        method: "POST",
        body: { invite_code: inviteCode.trim() },
        auth: true,
      });
      setInviteCode("");
      await fetchBoxData();
    } catch (err: any) {
      Alert.alert("Join Failed", err.message || "Invalid invite code.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleShareCode = async () => {
    if (!box?.invite_code) return;
    try {
      await Share.share({
        message: `Join our family nutrition challenge on Crack! Use invite code: ${box.invite_code}`,
      });
    } catch (e) {
      console.warn("Share error", e);
    }
  };

  const handleLeaveBox = () => {
    Alert.alert(
      "Leave Family Box?",
      "Are you sure you want to leave this group? Your individual logs will remain safe.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Leave",
          style: "destructive",
          onPress: async () => {
            try {
              await api("/family-box/leave", { method: "POST", auth: true });
              await fetchBoxData();
            } catch (err: any) {
              Alert.alert("Error", err.message || "Could not leave box.");
            }
          },
        },
      ]
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.brand} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      {/* Top Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Family Box</Text>
        {box ? (
          <Pressable onPress={handleLeaveBox} style={styles.leaveBtn}>
            <Ionicons name="log-out-outline" size={22} color={colors.error} />
          </Pressable>
        ) : (
          <View style={{ width: 40 }} />
        )}
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.brand} />}
      >
        {!box ? (
          /* State 1: User Not in a Box */
          <View style={styles.welcomeCard}>
            <View style={styles.trophyCircle}>
              <Ionicons name="people" size={40} color={colors.brand} />
            </View>
            <Text style={styles.welcomeTitle}>Family Nutrition Hub</Text>
            <Text style={styles.welcomeSub}>
              Track diets together with your household, hit your calorie targets, and compete on the daily leaderboard!
            </Text>

            {/* Mode Switcher */}
            <View style={styles.tabSwitcher}>
              <Pressable
                style={[styles.tabBtn, mode === "create" && styles.tabBtnActive]}
                onPress={() => setMode("create")}
              >
                <Text style={[styles.tabBtnText, mode === "create" && styles.tabBtnTextActive]}>
                  Create a Box
                </Text>
              </Pressable>
              <Pressable
                style={[styles.tabBtn, mode === "join" && styles.tabBtnActive]}
                onPress={() => setMode("join")}
              >
                <Text style={[styles.tabBtnText, mode === "join" && styles.tabBtnTextActive]}>
                  Join with Code
                </Text>
              </Pressable>
            </View>

            {mode === "create" ? (
              <View style={styles.formWrap}>
                <Text style={styles.inputLabel}>Group Name</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g. Lodhi Family or Fitness Squad"
                  placeholderTextColor={colors.muted}
                  value={boxName}
                  onChangeText={setBoxName}
                  maxLength={40}
                />
                <Pressable
                  style={[styles.primaryBtn, submitting && styles.btnDisabled]}
                  onPress={handleCreateBox}
                  disabled={submitting}
                >
                  {submitting ? (
                    <ActivityIndicator color={colors.onBrand} />
                  ) : (
                    <Text style={styles.primaryBtnText}>Create Family Box</Text>
                  )}
                </Pressable>
              </View>
            ) : (
              <View style={styles.formWrap}>
                <Text style={styles.inputLabel}>Enter Invite Code</Text>
                <TextInput
                  style={[styles.input, { letterSpacing: 2, textTransform: "uppercase" }]}
                  placeholder="e.g. FAM-ABCD"
                  placeholderTextColor={colors.muted}
                  value={inviteCode}
                  onChangeText={setInviteCode}
                  autoCapitalize="characters"
                  maxLength={12}
                />
                <Pressable
                  style={[styles.primaryBtn, submitting && styles.btnDisabled]}
                  onPress={handleJoinBox}
                  disabled={submitting}
                >
                  {submitting ? (
                    <ActivityIndicator color={colors.onBrand} />
                  ) : (
                    <Text style={styles.primaryBtnText}>Join Box</Text>
                  )}
                </Pressable>
              </View>
            )}
          </View>
        ) : (
          /* State 2: User In a Box -> Show Leaderboard */
          <View>
            {/* Box Header Card */}
            <View style={styles.boxHeaderCard}>
              <View style={styles.boxTitleRow}>
                <View>
                  <Text style={styles.boxName}>{box.name}</Text>
                  <Text style={styles.boxMembersCount}>{box.member_count} Members Active</Text>
                </View>
                <Pressable style={styles.shareBtn} onPress={handleShareCode}>
                  <Ionicons name="share-social" size={18} color={colors.brand} />
                  <Text style={styles.shareBtnText}>Share</Text>
                </Pressable>
              </View>

              <View style={styles.inviteCodeBadge}>
                <Text style={styles.inviteLabel}>Invite Code: </Text>
                <Text style={styles.inviteCodeText}>{box.invite_code}</Text>
              </View>
            </View>

            {/* Leaderboard Section */}
            <View style={styles.leaderboardSection}>
              <View style={styles.leaderboardHeader}>
                <Ionicons name="trophy" size={22} color={colors.warning} />
                <Text style={styles.sectionHeading}>Today's Leaderboard</Text>
              </View>
              <Text style={styles.sectionSubtitle}>
                Ranked by adherence % to individual daily calorie goals
              </Text>

              {leaderboard.map((member) => {
                const isFirst = member.rank === 1;
                const isSecond = member.rank === 2;
                const isThird = member.rank === 3;

                return (
                  <View
                    key={member.user_id}
                    style={[
                      styles.memberCard,
                      member.is_me && styles.memberCardMe,
                      isFirst && styles.memberCardFirst,
                    ]}
                  >
                    {/* Rank Badge */}
                    <View style={styles.rankCol}>
                      {isFirst ? (
                        <Text style={styles.medalEmoji}>🥇</Text>
                      ) : isSecond ? (
                        <Text style={styles.medalEmoji}>🥈</Text>
                      ) : isThird ? (
                        <Text style={styles.medalEmoji}>🥉</Text>
                      ) : (
                        <Text style={styles.rankNum}>#{member.rank}</Text>
                      )}
                    </View>

                    {/* Member Info */}
                    <View style={styles.memberInfoCol}>
                      <View style={styles.memberNameRow}>
                        <Text style={styles.memberName}>{member.name}</Text>
                        {member.is_me && <View style={styles.youBadge}><Text style={styles.youText}>YOU</Text></View>}
                      </View>

                      <View style={styles.goalRow}>
                        <Text style={styles.goalBadge}>
                          Goal: {member.goal.toUpperCase()}
                        </Text>
                        <Text style={styles.calProgressText}>
                          {member.calories_consumed} / {member.daily_target} kcal ({member.target_percentage}%)
                        </Text>
                      </View>

                      {/* Progress Bar */}
                      <View style={styles.progressBarBg}>
                        <View
                          style={[
                            styles.progressBarFill,
                            {
                              width: `${member.target_percentage}%`,
                              backgroundColor: isFirst ? "#EAB308" : colors.brand,
                            },
                          ]}
                        />
                      </View>
                    </View>

                    {/* Score / Points */}
                    <View style={styles.scoreCol}>
                      <Text style={styles.scoreNum}>{member.score}</Text>
                      <Text style={styles.scoreLabel}>pts</Text>
                    </View>
                  </View>
                );
              })}
            </View>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.surface2 },
  centerContainer: { flex: 1, justifyContent: "center", alignItems: "center" },
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
  leaveBtn: { padding: spacing.xs },
  headerTitle: { fontSize: 18, fontWeight: "700", color: colors.onSurface },
  scrollContent: { padding: spacing.lg },
  welcomeCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.xl,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  trophyCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.brandSoft,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  welcomeTitle: { fontSize: 22, fontWeight: "800", color: colors.onSurface, marginBottom: spacing.xs },
  welcomeSub: {
    fontSize: 14,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 20,
    marginBottom: spacing.xl,
  },
  tabSwitcher: {
    flexDirection: "row",
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
    padding: 4,
    width: "100%",
    marginBottom: spacing.lg,
  },
  tabBtn: { flex: 1, paddingVertical: 10, alignItems: "center", borderRadius: radius.sm },
  tabBtnActive: { backgroundColor: colors.surface },
  tabBtnText: { fontSize: 14, fontWeight: "600", color: colors.muted },
  tabBtnTextActive: { color: colors.onSurface, fontWeight: "700" },
  formWrap: { width: "100%" },
  inputLabel: { fontSize: 13, fontWeight: "600", color: colors.onSurface2, marginBottom: spacing.xs },
  input: {
    backgroundColor: colors.surface2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 12,
    fontSize: 15,
    color: colors.onSurface,
    marginBottom: spacing.lg,
  },
  primaryBtn: {
    backgroundColor: colors.brand,
    borderRadius: radius.md,
    paddingVertical: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  btnDisabled: { opacity: 0.6 },
  primaryBtnText: { color: colors.onBrand, fontSize: 15, fontWeight: "700" },
  boxHeaderCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.lg,
  },
  boxTitleRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  boxName: { fontSize: 20, fontWeight: "800", color: colors.onSurface },
  boxMembersCount: { fontSize: 13, color: colors.muted, marginTop: 2 },
  shareBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: colors.brandSoft,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
  },
  shareBtnText: { color: colors.brand, fontSize: 13, fontWeight: "700" },
  inviteCodeBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    marginTop: spacing.md,
  },
  inviteLabel: { fontSize: 13, color: colors.muted },
  inviteCodeText: { fontSize: 14, fontWeight: "800", color: colors.brand, letterSpacing: 1 },
  leaderboardSection: { marginTop: spacing.xs },
  leaderboardHeader: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 2 },
  sectionHeading: { fontSize: 18, fontWeight: "800", color: colors.onSurface },
  sectionSubtitle: { fontSize: 12, color: colors.muted, marginBottom: spacing.md },
  memberCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  memberCardMe: { borderColor: colors.brand, borderWidth: 1.5 },
  memberCardFirst: { backgroundColor: "#FFFDF7", borderColor: "#FDE047" },
  rankCol: { width: 36, alignItems: "center", justifyContent: "center" },
  medalEmoji: { fontSize: 22 },
  rankNum: { fontSize: 15, fontWeight: "700", color: colors.muted },
  memberInfoCol: { flex: 1, paddingHorizontal: spacing.sm },
  memberNameRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  memberName: { fontSize: 15, fontWeight: "700", color: colors.onSurface },
  youBadge: { backgroundColor: colors.brand, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  youText: { color: colors.onBrand, fontSize: 9, fontWeight: "800" },
  goalRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginVertical: 4 },
  goalBadge: { fontSize: 11, fontWeight: "600", color: colors.muted },
  calProgressText: { fontSize: 11, color: colors.onSurface2, fontWeight: "500" },
  progressBarBg: { height: 6, backgroundColor: colors.surface2, borderRadius: 3, overflow: "hidden" },
  progressBarFill: { height: "100%", borderRadius: 3 },
  scoreCol: { alignItems: "flex-end", minWidth: 50 },
  scoreNum: { fontSize: 18, fontWeight: "800", color: colors.brand },
  scoreLabel: { fontSize: 10, color: colors.muted, fontWeight: "600" },
});