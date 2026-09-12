import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, radius } from "@/src/theme";
import { StreakData } from "@/src/streak";

type StreakCardProps = {
  data: StreakData | null;
  loading?: boolean;
};

export function StreakCard({ data, loading }: StreakCardProps) {
  if (loading) {
    return (
      <View style={styles.card} testID="streak-card-skeleton">
        <View style={styles.headerRow}>
          <View style={styles.badgePlaceholder} />
          <View style={styles.pillPlaceholder} />
        </View>
        <View style={styles.textPlaceholder} />
        <View style={styles.weekRowPlaceholder} />
      </View>
    );
  }

  if (!data) return null;

  const { current_streak, longest_streak, logged_today, streak_active, weekly_activity, message } = data;

  return (
    <View style={styles.card} testID="streak-card">
      <View style={styles.headerRow}>
        <View style={styles.streakBadge}>
          <View style={[styles.flameIconWrap, streak_active && styles.flameIconWrapActive]}>
            <Text style={styles.flameEmoji}>{streak_active ? "🔥" : "⚡"}</Text>
          </View>
          <View>
            <Text style={styles.streakCount} testID="streak-count">
              {current_streak} {current_streak === 1 ? "Day" : "Days"}
            </Text>
            <Text style={styles.streakStatusLabel}>
              {logged_today ? "Streak active today" : streak_active ? "Keep it alive!" : "Daily Streak"}
            </Text>
          </View>
        </View>

        {longest_streak > 0 && (
          <View style={styles.bestPill} testID="streak-best">
            <Ionicons name="trophy" size={13} color="#D97706" style={{ marginRight: 4 }} />
            <Text style={styles.bestTxt}>Best: {longest_streak}d</Text>
          </View>
        )}
      </View>

      <Text style={styles.messageTxt} testID="streak-message" numberOfLines={2}>
        {message}
      </Text>

      {/* 7-Day Weekly Progress Bar */}
      <View style={styles.weekContainer} testID="streak-weekly-activity">
        {weekly_activity.map((item) => {
          const isToday = item.is_today;
          const isLogged = item.logged;

          return (
            <View
              key={item.date}
              style={[
                styles.dayColumn,
                isToday && styles.dayColumnToday,
              ]}
              testID={`streak-day-${item.date}`}
            >
              <Text
                style={[
                  styles.dayLetter,
                  isToday && styles.dayLetterToday,
                  isLogged && styles.dayLetterLogged,
                ]}
              >
                {item.day_name}
              </Text>

              <View
                style={[
                  styles.dot,
                  isLogged ? styles.dotLogged : styles.dotEmpty,
                  isToday && !isLogged && styles.dotTodayPending,
                ]}
              >
                {isLogged ? (
                  <Ionicons name="checkmark" size={12} color="#FFFFFF" />
                ) : isToday ? (
                  <Ionicons name="add" size={12} color={colors.brand} />
                ) : (
                  <View style={styles.dotInnerMuted} />
                )}
              </View>
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#FFF8F5",
    borderWidth: 1.5,
    borderColor: "#FDD8CE",
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginVertical: spacing.sm,
    shadowColor: colors.brand,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 2,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.xs,
  },
  streakBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  flameIconWrap: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#FEE2E2",
    alignItems: "center",
    justifyContent: "center",
  },
  flameIconWrapActive: {
    backgroundColor: "#FFEDD5",
    borderWidth: 1.5,
    borderColor: "#FDBA74",
  },
  flameEmoji: {
    fontSize: 20,
  },
  streakCount: {
    fontSize: 20,
    fontWeight: "800",
    color: colors.onSurface,
    lineHeight: 24,
  },
  streakStatusLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.brandDark,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  bestPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FEF3C7",
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: "#FDE68A",
  },
  bestTxt: {
    fontSize: 11,
    fontWeight: "700",
    color: "#B45309",
  },
  messageTxt: {
    fontSize: 13,
    color: colors.onSurface2,
    marginTop: spacing.xs,
    marginBottom: spacing.md,
    lineHeight: 18,
  },
  weekContainer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: "#FEECE7",
  },
  dayColumn: {
    alignItems: "center",
    gap: 4,
    paddingVertical: 2,
    paddingHorizontal: 4,
    borderRadius: radius.sm,
  },
  dayColumnToday: {
    backgroundColor: "#FFF1EC",
  },
  dayLetter: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.muted,
  },
  dayLetterToday: {
    fontWeight: "800",
    color: colors.brand,
  },
  dayLetterLogged: {
    color: colors.brandDark,
  },
  dot: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: "center",
    justifyContent: "center",
  },
  dotLogged: {
    backgroundColor: colors.brand,
    shadowColor: colors.brand,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3,
    elevation: 2,
  },
  dotEmpty: {
    backgroundColor: colors.surface2,
  },
  dotTodayPending: {
    backgroundColor: "#FFE4DC",
    borderWidth: 1.5,
    borderColor: colors.brand,
    borderStyle: "dashed",
  },
  dotInnerMuted: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.borderStrong,
  },
  // Skeletons
  badgePlaceholder: {
    width: 120,
    height: 32,
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
  },
  pillPlaceholder: {
    width: 70,
    height: 24,
    backgroundColor: colors.surface2,
    borderRadius: radius.pill,
  },
  textPlaceholder: {
    width: "70%",
    height: 14,
    backgroundColor: colors.surface2,
    borderRadius: radius.sm,
    marginVertical: spacing.md,
  },
  weekRowPlaceholder: {
    width: "100%",
    height: 48,
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
  },
});
