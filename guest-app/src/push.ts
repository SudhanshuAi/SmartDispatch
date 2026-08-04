import { Platform } from "react-native";
import type { AuthUser } from "../types";
import { api } from "../api/client";

/**
 * Register Expo push token with the backend when permissions allow.
 * No-ops quietly on web / denied / missing native module.
 */
export async function registerGuestPush(user: AuthUser): Promise<void> {
  if (Platform.OS === "web") return;
  try {
    const Notifications = await import("expo-notifications");
    const { status: existing } = await Notifications.getPermissionsAsync();
    let finalStatus = existing;
    if (existing !== "granted") {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }
    if (finalStatus !== "granted") return;
    const tokenData = await Notifications.getExpoPushTokenAsync();
    const token = tokenData?.data;
    if (token) await api.registerPushToken(user, token);
  } catch {
    /* demo-safe: push is best-effort */
  }
}
