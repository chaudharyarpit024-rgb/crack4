import { Tabs } from "expo-router";
  import { Ionicons } from "@expo/vector-icons";
  import { useSafeAreaInsets } from "react-native-safe-area-context";           // ← NEW
  import { colors } from "@/src/theme";

  export default function TabsLayout() {
    const insets = useSafeAreaInsets();                                          // ← NEW

    return (
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: colors.brand,
          tabBarInactiveTintColor: colors.muted,
          tabBarStyle: {
            backgroundColor: colors.surface,
            borderTopColor: colors.divider,
            height: 68 + insets.bottom,                                          // ← CHANGED
            paddingBottom: 10 + insets.bottom,                                   // ← CHANGED
            paddingTop: 8,
          },
          tabBarLabelStyle: { fontSize: 11, fontWeight: "600" },
        }}
      >
        <Tabs.Screen
          name="index"
          options={{
            title: "Home",
            tabBarIcon: ({ color, size }) => <Ionicons name="home" size={size} color={color} />,
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            title: "Profile",
            tabBarIcon: ({ color, size }) => <Ionicons name="person" size={size} color={color} />,
          }}
        />
      </Tabs>
    );
  }