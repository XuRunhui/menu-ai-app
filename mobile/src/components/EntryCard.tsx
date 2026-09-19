import React from 'react';
import {
  TouchableOpacity,
  View,
  Text,
  StyleSheet,
  ViewStyle,
} from 'react-native';
import { Colors, Radius, Spacing, Typography } from '@/theme';

interface EntryCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  onPress?: () => void;
  disabled?: boolean;
  style?: ViewStyle;
}

export default function EntryCard({
  icon,
  title,
  description,
  onPress,
  disabled = false,
  style,
}: EntryCardProps) {
  return (
    <TouchableOpacity
      onPress={disabled ? undefined : onPress}
      activeOpacity={disabled ? 1 : 0.7}
      style={[styles.card, disabled && styles.cardDisabled, style]}
    >
      {/* Icon */}
      <View style={styles.iconWrap}>{icon}</View>

      {/* Text */}
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.description}>{description}</Text>

      {/* Disabled badge */}
      {disabled && (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>COMING SOON</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.card,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.lg,
    marginBottom: Spacing.md,
    // iOS shadow
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 3,
  },
  cardDisabled: {
    opacity: 0.45,
  },
  iconWrap: {
    width: 48,
    height: 48,
    borderRadius: Radius.md,
    backgroundColor: Colors.primaryDim,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.md,
  },
  title: {
    ...Typography.h3,
    marginBottom: Spacing.xs,
  },
  description: {
    ...Typography.bodySecondary,
    lineHeight: 19,
  },
  badge: {
    marginTop: Spacing.sm,
    alignSelf: 'flex-start',
    backgroundColor: Colors.surface,
    borderRadius: Radius.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
  },
  badgeText: {
    ...Typography.label,
    color: Colors.primary,
  },
});
