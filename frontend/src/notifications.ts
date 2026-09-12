import * as Notifications from "expo-notifications";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";

const REMINDER_KEY = "streak_reminder_enabled";
const DEFAULT_HOUR = 20; // 8 PM
const DEFAULT_MINUTE = 0;

const REMINDER_MESSAGES = [
  "Don't break your streak! 🔥 Log your meals today.",
  "Keep the momentum going! 📈 Track your food now.",
  "Your streak is waiting! 💪 Open Crack and log a meal.",
  "Stay consistent! 🎯 A quick log keeps your streak alive.",
  "Almost forgot? 🍽️ Log what you ate today!",
];

/** Configure how notifications appear when the app is in the foreground. */
export function configureNotificationHandler() {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldPlaySound: false,
      shouldSetBadge: false,
      shouldShowBanner: true,
      shouldShowList: true,
    }),
  });
}

/** Request notification permissions. Returns true if granted. */
export async function requestPermissions(): Promise<boolean> {
  if (Platform.OS === "web") return false;

  const { status: existing } = await Notifications.getPermissionsAsync();
  if (existing === "granted") return true;

  const { status } = await Notifications.requestPermissionsAsync();
  return status === "granted";
}

/** Set up the Android notification channel (required for Android 8+). */
export async function ensureChannel() {
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("streak-reminder", {
      name: "Streak Reminders",
      importance: Notifications.AndroidImportance.HIGH,
      sound: "default",
      vibrationPattern: [0, 250, 250, 250],
    });
  }
}

/** Schedule a daily repeating notification at 8 PM local time. */
export async function scheduleStreakReminder() {
  // Cancel any existing reminders first to avoid duplicates.
  await Notifications.cancelAllScheduledNotificationsAsync();

  const message =
    REMINDER_MESSAGES[Math.floor(Math.random() * REMINDER_MESSAGES.length)];

  await Notifications.scheduleNotificationAsync({
    content: {
      title: "Crack — Track It First",
      body: message,
      sound: "default",
      ...(Platform.OS === "android" && { channelId: "streak-reminder" }),
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.DAILY,
      hour: DEFAULT_HOUR,
      minute: DEFAULT_MINUTE,
    },
  });

  await AsyncStorage.setItem(REMINDER_KEY, "true");
}

/** Cancel all scheduled streak reminders. */
export async function cancelStreakReminder() {
  await Notifications.cancelAllScheduledNotificationsAsync();
  await AsyncStorage.setItem(REMINDER_KEY, "false");
}

/** Check whether reminders are currently enabled. */
export async function isReminderEnabled(): Promise<boolean> {
  const val = await AsyncStorage.getItem(REMINDER_KEY);
  // Default to true (opt-in on first launch).
  return val !== "false";
}

/**
 * One-shot initializer — call once from app root.
 * Requests permissions, sets up the channel, and schedules the reminder
 * if the user hasn't explicitly disabled it.
 */
export async function initNotifications() {
  configureNotificationHandler();
  const granted = await requestPermissions();
  if (!granted) return;

  await ensureChannel();

  const enabled = await isReminderEnabled();
  if (enabled) {
    await scheduleStreakReminder();
  }
}
