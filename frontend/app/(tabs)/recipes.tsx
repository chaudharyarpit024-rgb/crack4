import React, { useState, useEffect, useCallback } from "react";
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    Pressable,
    ActivityIndicator,
    RefreshControl,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import { colors, spacing, radius } from "@/src/theme";
import { api } from "@/src/api";
import { isNetworkError, isAuthError } from "@/src/utils/network";

interface Recipe {
    id: string;
    title: string;
    meal_type: string;
    calories: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
    prep_time_minutes: number;
    difficulty: string;
    description: string;
    ingredients: string[];
    instructions: string[];
    why_it_fits: string;
}

interface RecipesResponse {
    remaining_calories: number;
    diet_preference: string;
    meal_type?: string;
    recipes: Recipe[];
}

const MEAL_TYPES = [
    { id: "all", label: "All Meals" },
    { id: "breakfast", label: "Breakfast" },
    { id: "lunch", label: "Lunch" },
    { id: "dinner", label: "Dinner" },
    { id: "snack", label: "Snack" },
];

export default function RecipesScreen() {
    const router = useRouter();
    const [selectedMeal, setSelectedMeal] = useState("all");
    const [recipes, setRecipes] = useState<Recipe[]>([]);
    const [remainingCalories, setRemainingCalories] = useState<number>(0);
    const [loading, setLoading] = useState<boolean>(true);
    const [refreshing, setRefreshing] = useState<boolean>(false);
    const [expandedId, setExpandedId] = useState<string | null>(null);

    const fetchRecipes = useCallback(
        async (meal: string) => {
            try {
                let path = "/nutrition/recipes";
                if (meal !== "all") {
                    path += `?meal_type=${meal}`;
                }
                const data = await api<RecipesResponse>(path);
                setRecipes(data.recipes || []);
                setRemainingCalories(data.remaining_calories || 0);
            } catch (err: any) {
                if (isNetworkError(err)) {
                    router.replace("/network-error");
                } else if (isAuthError(err)) {
                    router.replace("/session-expired");
                } else if (err?.status === 403) {
                    // Gated feature for subscribers
                    router.push({ pathname: "/subscribe", params: { reason: "recipes" } });
                }
            } finally {
                setLoading(false);
                setRefreshing(false);
            }
        },
        [router]
    );

    useEffect(() => {
        setLoading(true);
        fetchRecipes(selectedMeal);
    }, [selectedMeal, fetchRecipes]);

    const toggleExpand = (id: string) => {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        setExpandedId((prev) => (prev === id ? null : id));
    };

    return (
        <SafeAreaView style={styles.safe} edges={["top"]}>
            {/* Top Header */}
            <View style={styles.header}>
                <Pressable
                    onPress={() => router.back()}
                    style={styles.backBtn}
                    testID="recipes-back-btn"
                >
                    <Ionicons name="arrow-back" size={24} color={colors.onSurface} />
                </Pressable>
                <Text style={styles.headerTitle}>Recipe Suggestions</Text>
                <View style={{ width: 40 }} />
            </View>

            {/* Remaining Calories Pill */}
            <View style={styles.calorieBanner}>
                <Ionicons name="flame" size={20} color={colors.brand} />
                <Text style={styles.calorieBannerText}>
                    Target: <Text style={styles.calorieBold}>{remainingCalories} kcal</Text> remaining today
                </Text>
            </View>

            {/* Filter Tabs */}
            <View style={styles.filterWrap}>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterBar}>
                    {MEAL_TYPES.map((type) => {
                        const active = selectedMeal === type.id;
                        return (
                            <Pressable
                                key={type.id}
                                onPress={() => {
                                    Haptics.selectionAsync();
                                    setSelectedMeal(type.id);
                                }}
                                style={[styles.filterChip, active && styles.filterChipActive]}
                            >
                                <Text style={[styles.filterChipText, active && styles.filterChipTextActive]}>
                                    {type.label}
                                </Text>
                            </Pressable>
                        );
                    })}
                </ScrollView>
            </View>

            {/* Content */}
            {loading ? (
                <View style={styles.centerContainer}>
                    <ActivityIndicator size="large" color={colors.brand} />
                    <Text style={styles.loadingText}>Crafting personalized meals...</Text>
                </View>
            ) : (
                <ScrollView
                    contentContainerStyle={styles.scrollList}
                    refreshControl={
                        <RefreshControl
                            refreshing={refreshing}
                            onRefresh={() => {
                                setRefreshing(true);
                                fetchRecipes(selectedMeal);
                            }}
                        />
                    }
                >
                    {recipes.length === 0 ? (
                        <View style={styles.emptyState}>
                            <Ionicons name="restaurant-outline" size={48} color={colors.muted} />
                            <Text style={styles.emptyTitle}>No recipes found</Text>
                            <Text style={styles.emptySub}>
                                Try selecting a different meal filter above.
                            </Text>
                        </View>
                    ) : (
                        recipes.map((item) => {
                            const isExpanded = expandedId === item.id;
                            return (
                                <View key={item.id} style={styles.card}>
                                    <Pressable onPress={() => toggleExpand(item.id)} style={styles.cardHeader}>
                                        <View style={{ flex: 1 }}>
                                            <View style={styles.tagRow}>
                                                <View style={styles.mealBadge}>
                                                    <Text style={styles.mealBadgeText}>{item.meal_type.toUpperCase()}</Text>
                                                </View>
                                                <Text style={styles.prepTime}>
                                                    <Ionicons name="time-outline" size={13} color={colors.muted} /> {item.prep_time_minutes}m
                                                </Text>
                                                <Text style={styles.difficulty}>• {item.difficulty}</Text>
                                            </View>
                                            <Text style={styles.cardTitle}>{item.title}</Text>
                                            <Text style={styles.cardDesc} numberOfLines={isExpanded ? undefined : 2}>
                                                {item.description}
                                            </Text>
                                        </View>
                                        <Ionicons
                                            name={isExpanded ? "chevron-up" : "chevron-down"}
                                            size={20}
                                            color={colors.muted}
                                            style={{ marginLeft: 8 }}
                                        />
                                    </Pressable>

                                    {/* Macro Row */}
                                    <View style={styles.macroRow}>
                                        <View style={styles.macroPill}>
                                            <Text style={styles.macroLabel}>Calories</Text>
                                            <Text style={styles.macroVal}>{item.calories} kcal</Text>
                                        </View>
                                        <View style={styles.macroPill}>
                                            <Text style={styles.macroLabel}>Protein</Text>
                                            <Text style={styles.macroVal}>{item.protein_g}g</Text>
                                        </View>
                                        <View style={styles.macroPill}>
                                            <Text style={styles.macroLabel}>Carbs</Text>
                                            <Text style={styles.macroVal}>{item.carbs_g}g</Text>
                                        </View>
                                        <View style={styles.macroPill}>
                                            <Text style={styles.macroLabel}>Fat</Text>
                                            <Text style={styles.macroVal}>{item.fat_g}g</Text>
                                        </View>
                                    </View>

                                    {/* Expandable Details */}
                                    {isExpanded && (
                                        <View style={styles.expandedSection}>
                                            {item.why_it_fits ? (
                                                <View style={styles.whyBox}>
                                                    <Ionicons name="bulb-outline" size={16} color={colors.brand} />
                                                    <Text style={styles.whyText}>{item.why_it_fits}</Text>
                                                </View>
                                            ) : null}

                                            <Text style={styles.subHeading}>Ingredients:</Text>
                                            {item.ingredients.map((ing, idx) => (
                                                <Text key={idx} style={styles.bulletItem}>
                                                    • {ing}
                                                </Text>
                                            ))}

                                            <Text style={[styles.subHeading, { marginTop: spacing.md }]}>Instructions:</Text>
                                            {item.instructions.map((step, idx) => (
                                                <Text key={idx} style={styles.stepItem}>
                                                    <Text style={styles.stepNumber}>{idx + 1}. </Text>
                                                    {step}
                                                </Text>
                                            ))}
                                        </View>
                                    )}
                                </View>
                            );
                        })
                    )}
                    <View style={{ height: 40 }} />
                </ScrollView>
            )}
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    safe: { flex: 1, backgroundColor: colors.surface },
    header: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        paddingHorizontal: spacing.lg,
        paddingVertical: spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: colors.border,
    },
    backBtn: { padding: spacing.xs },
    headerTitle: { fontSize: 18, fontWeight: "700", color: colors.onSurface },
    calorieBanner: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: colors.brandSoft,
        paddingVertical: spacing.sm,
        paddingHorizontal: spacing.lg,
        gap: spacing.xs,
    },
    calorieBannerText: { fontSize: 13, color: colors.brandDark },
    calorieBold: { fontWeight: "800", color: colors.brand },
    filterWrap: {
        borderBottomWidth: 1,
        borderBottomColor: colors.border,
        backgroundColor: colors.surface,
    },
    filterBar: {
        paddingHorizontal: spacing.lg,
        paddingVertical: spacing.sm,
        gap: spacing.sm,
    },
    filterChip: {
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.xs,
        borderRadius: radius.pill,
        backgroundColor: colors.surface2,
    },
    filterChipActive: { backgroundColor: colors.brand },
    filterChipText: { fontSize: 13, color: colors.onSurface2, fontWeight: "600" },
    filterChipTextActive: { color: colors.onBrand },
    centerContainer: { flex: 1, justifyContent: "center", alignItems: "center" },
    loadingText: { marginTop: spacing.md, fontSize: 14, color: colors.muted },
    scrollList: { padding: spacing.lg, gap: spacing.md },
    card: {
        backgroundColor: colors.surface,
        borderRadius: radius.md,
        borderWidth: 1,
        borderColor: colors.border,
        padding: spacing.md,
        shadowColor: "#000",
        shadowOpacity: 0.05,
        shadowRadius: 4,
        elevation: 2,
    },
    cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
    tagRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs, marginBottom: spacing.xs },
    mealBadge: {
        backgroundColor: colors.brandSoft,
        paddingHorizontal: 6,
        paddingVertical: 2,
        borderRadius: 4,
    },
    mealBadgeText: { fontSize: 10, fontWeight: "800", color: colors.brand },
    prepTime: { fontSize: 12, color: colors.muted },
    difficulty: { fontSize: 12, color: colors.muted, textTransform: "capitalize" },
    cardTitle: { fontSize: 16, fontWeight: "700", color: colors.onSurface, marginBottom: 4 },
    cardDesc: { fontSize: 13, color: colors.onSurface2, lineHeight: 18 },
    macroRow: {
        flexDirection: "row",
        justifyContent: "space-between",
        marginTop: spacing.md,
        paddingTop: spacing.sm,
        borderTopWidth: 1,
        borderTopColor: colors.surface2,
    },
    macroPill: { alignItems: "center" },
    macroLabel: { fontSize: 11, color: colors.muted },
    macroVal: { fontSize: 13, fontWeight: "700", color: colors.onSurface, marginTop: 2 },
    expandedSection: {
        marginTop: spacing.md,
        paddingTop: spacing.md,
        borderTopWidth: 1,
        borderTopColor: colors.border,
    },
    whyBox: {
        flexDirection: "row",
        backgroundColor: colors.surface2,
        padding: spacing.sm,
        borderRadius: radius.sm,
        gap: spacing.xs,
        marginBottom: spacing.md,
        alignItems: "center",
    },
    whyText: { flex: 1, fontSize: 12, color: colors.onSurface2, fontStyle: "italic" },
    subHeading: { fontSize: 14, fontWeight: "700", color: colors.onSurface, marginBottom: spacing.xs },
    bulletItem: { fontSize: 13, color: colors.onSurface2, lineHeight: 20, marginLeft: 4 },
    stepItem: { fontSize: 13, color: colors.onSurface2, lineHeight: 20, marginBottom: 4 },
    stepNumber: { fontWeight: "700", color: colors.brand },
    emptyState: { alignItems: "center", marginTop: 60, paddingHorizontal: spacing.xl },
    emptyTitle: { fontSize: 16, fontWeight: "700", color: colors.onSurface, marginTop: spacing.md },
    emptySub: { fontSize: 13, color: colors.muted, textAlign: "center", marginTop: 4 },
});
