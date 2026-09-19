import React, { useState, useMemo } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '@/navigation/AppNavigator';
import { useAppContext } from '@/store/AppContext';
import DishCard from '@/components/DishCard';
import CategoryTabs from '@/components/CategoryTabs';
import { Colors, Radius, Spacing, Typography } from '@/theme';
import type { MenuCategory, MenuItem, PopularDish } from '@/types';

type NavProp = StackNavigationProp<RootStackParamList, 'Restaurant'>;

function popularDishToMenuItem(dish: PopularDish): MenuItem {
  return {
    name: dish.name,
    description: dish.sample_reviews?.[0] ?? null,
    price: null,
    price_original: null,
    currency: null,
  };
}

function StarRating({ rating }: { rating: number }) {
  const stars = Math.round(rating);
  return (
    <Text style={styles.stars}>
      {'★'.repeat(stars)}{'☆'.repeat(5 - stars)}
    </Text>
  );
}

export default function RestaurantScreen({ navigation }: { navigation: NavProp }) {
  const {
    restaurant,
    parsedMenu,
    popularDishes,
    targetLanguage,
    knowledgeBaseStatus,
    checkIsRecommended,
  } = useAppContext();

  const [activeTab, setActiveTab] = useState<'dishes' | 'combo'>('dishes');
  const [activeCatIdx, setActiveCatIdx] = useState(0);
  const showTranslation = Boolean(targetLanguage);

  // Build categories — parsed menu wins over popular dishes
  const categories: MenuCategory[] = useMemo(() => {
    if (parsedMenu?.menu && parsedMenu.menu.length > 0) return parsedMenu.menu;
    if (popularDishes.length > 0) {
      return [{ category: 'Popular Dishes', items: popularDishes.map(popularDishToMenuItem) }];
    }
    return [];
  }, [parsedMenu, popularDishes]);

  const categoryLabels = categories.map((c) =>
    (showTranslation && c.category_translated) ? c.category_translated : c.category,
  );

  const activeItems = categories[activeCatIdx]?.items ?? [];

  const renderDish = ({ item, index }: { item: MenuItem; index: number }) => (
    <View style={index % 2 === 0 ? styles.cellLeft : styles.cellRight}>
      <DishCard
        item={item}
        isRecommended={checkIsRecommended(item.name)}
        restaurantName={restaurant?.name}
        showTranslation={showTranslation}
      />
    </View>
  );

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" backgroundColor={Colors.bg} />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backArrow}>←</Text>
        </TouchableOpacity>
        <View style={styles.headerInfo}>
          <Text style={styles.restaurantName} numberOfLines={1}>
            {restaurant?.name ?? 'Results'}
          </Text>
          {restaurant?.rating != null && (
            <View style={styles.ratingRow}>
              <StarRating rating={restaurant.rating} />
              {knowledgeBaseStatus === 'building' && (
                <Text style={styles.kbStatus}>  · Building AI context…</Text>
              )}
              {knowledgeBaseStatus === 'ready' && (
                <Text style={styles.kbReady}>  · AI ready</Text>
              )}
            </View>
          )}
        </View>
      </View>

      {/* Tab switcher */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          onPress={() => setActiveTab('dishes')}
          style={[styles.tabBtn, activeTab === 'dishes' && styles.tabBtnActive]}
        >
          <Text style={[styles.tabLabel, activeTab === 'dishes' && styles.tabLabelActive]}>
            Dish List
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => setActiveTab('combo')}
          style={[styles.tabBtn, activeTab === 'combo' && styles.tabBtnActive]}
        >
          <Text style={[styles.tabLabel, activeTab === 'combo' && styles.tabLabelActive]}>
            Combo Recommendations
          </Text>
        </TouchableOpacity>
      </View>

      {activeTab === 'dishes' ? (
        <>
          {/* Category tabs */}
          {categoryLabels.length > 1 && (
            <CategoryTabs
              categories={categoryLabels}
              activeIndex={activeCatIdx}
              onSelect={(i) => setActiveCatIdx(i)}
            />
          )}

          {/* Dish grid */}
          <FlatList
            data={activeItems}
            keyExtractor={(item, idx) => `${item.name}-${idx}`}
            numColumns={2}
            renderItem={renderDish}
            contentContainerStyle={styles.grid}
            showsVerticalScrollIndicator={false}
            ListEmptyComponent={
              <Text style={styles.emptyText}>No dishes found in this category.</Text>
            }
          />
        </>
      ) : (
        /* Combo placeholder */
        <View style={styles.comboPlaceholder}>
          <Text style={styles.comboIcon}>✨</Text>
          <Text style={styles.comboTitle}>Combo Recommendations</Text>
          <Text style={styles.comboSubtitle}>
            AI-powered meal combos are coming soon. We'll suggest the perfect set based on your preferences.
          </Text>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderColor: Colors.border,
    gap: Spacing.sm,
  },
  backBtn: { padding: Spacing.sm, marginLeft: -Spacing.sm },
  backArrow: { fontSize: 22, color: Colors.textPrimary },
  headerInfo: { flex: 1 },
  restaurantName: { ...Typography.h3 },
  ratingRow: { flexDirection: 'row', alignItems: 'center', marginTop: 2 },
  stars: { color: Colors.primary, fontSize: 12 },
  kbStatus: { ...Typography.caption, color: Colors.textSecondary },
  kbReady: { ...Typography.caption, color: Colors.success },
  tabBar: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xs,
    gap: Spacing.xs,
    borderBottomWidth: 1,
    borderColor: Colors.border,
  },
  tabBtn: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  tabBtnActive: {
    backgroundColor: Colors.surface,
    borderColor: Colors.border,
  },
  tabLabel: { ...Typography.caption, color: Colors.textSecondary, fontWeight: '500' },
  tabLabelActive: { color: Colors.textPrimary, fontWeight: '600' },
  grid: {
    paddingHorizontal: Spacing.sm,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xl,
  },
  cellLeft: { flex: 1, paddingRight: Spacing.xs / 2 },
  cellRight: { flex: 1, paddingLeft: Spacing.xs / 2 },
  emptyText: {
    ...Typography.bodySecondary,
    textAlign: 'center',
    marginTop: Spacing.xl,
  },
  comboPlaceholder: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.xl,
    gap: Spacing.md,
  },
  comboIcon: { fontSize: 48 },
  comboTitle: { ...Typography.h2, textAlign: 'center' },
  comboSubtitle: { ...Typography.bodySecondary, textAlign: 'center' },
});
