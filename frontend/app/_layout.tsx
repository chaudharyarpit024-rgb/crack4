import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useEffect } from "react";
import { LogBox } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { GestureHandlerRootView } from "react-native-gesture-handler";

import { useIconFonts } from "@/src/hooks/use-icon-fonts";
import { initNotifications } from "@/src/notifications";

LogBox.ignoreAllLogs(true);

SplashScreen.preventAutoHideAsync().catch(() => {});

// Initialize notification permissions + daily streak reminder on cold start.
initNotifications().catch(() => {});

export default function RootLayout() {
  const [loaded, error] = useIconFonts();

  useEffect(() => {
    if (loaded || error) {
      SplashScreen.hideAsync().catch(() => {});
    }
  }, [loaded, error]);

  if (!loaded && !error) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <Stack screenOptions={{ headerShown: false, animation: "fade" }} />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
