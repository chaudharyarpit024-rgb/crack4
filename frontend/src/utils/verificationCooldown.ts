import AsyncStorage from "@react-native-async-storage/async-storage";

const STORAGE_KEY_PREFIX = "crack_verification_cooldown_";
const inMemoryCooldowns = new Map<string, number>();

function normalizeKey(email?: string): string {
  return (email || "__latest__").trim().toLowerCase();
}

/**
 * Start or update verification cooldown for an email (default: 60 seconds).
 */
export async function startVerificationCooldown(email?: string, seconds: number = 60): Promise<number> {
  const duration = Math.max(1, seconds);
  const endTime = Date.now() + duration * 1000;
  const key = normalizeKey(email);

  inMemoryCooldowns.set(key, endTime);
  inMemoryCooldowns.set("__latest__", endTime);

  try {
    await AsyncStorage.setItem(`${STORAGE_KEY_PREFIX}${key}`, String(endTime));
    if (key !== "__latest__") {
      await AsyncStorage.setItem(`${STORAGE_KEY_PREFIX}__latest__`, String(endTime));
    }
  } catch {
    // In-memory fallback will work even if persistent storage fails
  }

  return duration;
}

/**
 * Get remaining cooldown seconds synchronously from in-memory cache.
 */
export function getVerificationCooldownSync(email?: string): number {
  const key = normalizeKey(email);
  const endTime = inMemoryCooldowns.get(key) ?? inMemoryCooldowns.get("__latest__");
  if (!endTime) return 0;
  const remaining = Math.ceil((endTime - Date.now()) / 1000);
  return Math.max(0, remaining);
}

/**
 * Get remaining cooldown seconds asynchronously, checking persistent storage if needed.
 */
export async function getVerificationCooldown(email?: string): Promise<number> {
  const syncVal = getVerificationCooldownSync(email);
  if (syncVal > 0) return syncVal;

  const key = normalizeKey(email);
  try {
    const raw =
      (await AsyncStorage.getItem(`${STORAGE_KEY_PREFIX}${key}`)) ||
      (await AsyncStorage.getItem(`${STORAGE_KEY_PREFIX}__latest__`));
    if (!raw) return 0;
    const endTime = parseInt(raw, 10);
    if (!endTime || isNaN(endTime)) return 0;

    inMemoryCooldowns.set(key, endTime);
    const remaining = Math.ceil((endTime - Date.now()) / 1000);
    return Math.max(0, remaining);
  } catch {
    return 0;
  }
}

/**
 * Clear cooldown (e.g. after successful verification or reset).
 */
export async function clearVerificationCooldown(email?: string): Promise<void> {
  const key = normalizeKey(email);
  inMemoryCooldowns.delete(key);
  inMemoryCooldowns.delete("__latest__");
  try {
    await AsyncStorage.removeItem(`${STORAGE_KEY_PREFIX}${key}`);
    await AsyncStorage.removeItem(`${STORAGE_KEY_PREFIX}__latest__`);
  } catch {
    // Ignore
  }
}
