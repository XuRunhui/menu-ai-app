import React from 'react';
import {
  ScrollView,
  TouchableOpacity,
  Text,
  StyleSheet,
} from 'react-native';
import { Colors, Radius, Spacing, Typography } from '@/theme';

interface CategoryTabsProps {
  categories: string[];
  activeIndex: number;
  onSelect: (index: number) => void;
}

export default function CategoryTabs({ categories, activeIndex, onSelect }: CategoryTabsProps) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.container}
    >
      {categories.map((cat, i) => {
        const active = i === activeIndex;
        return (
          <TouchableOpacity
            key={`${cat}-${i}`}
            onPress={() => onSelect(i)}
            activeOpacity={0.7}
            style={[styles.pill, active ? styles.pillActive : styles.pillInactive]}
          >
            <Text style={[styles.label, active ? styles.labelActive : styles.labelInactive]}>
              {cat}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: Spacing.md,
    gap: Spacing.sm,
    paddingVertical: Spacing.xs,
  },
  pill: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.xl,
    borderWidth: 1,
  },
  pillActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  pillInactive: {
    backgroundColor: 'transparent',
    borderColor: Colors.border,
  },
  label: {
    ...Typography.caption,
    fontWeight: '500',
  },
  labelActive: {
    color: Colors.bg,
    fontWeight: '600',
  },
  labelInactive: {
    color: Colors.textSecondary,
  },
});
