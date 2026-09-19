import React, { useState, useEffect } from 'react';
import {
  TouchableOpacity,
  View,
  Text,
  Image,
  StyleSheet,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '@/navigation/AppNavigator';
import { getDishImage } from '@/api/client';
import { Colors, Radius, Spacing, Typography } from '@/theme';
import type { MenuItem } from '@/types';

// Deterministic gradient index from dish name
const GRADIENTS: [string, string][] = [
  ['#3D2B1F', '#1A0F00'],
  ['#1F2B3D', '#001A2B'],
  ['#2B1F3D', '#1A002B'],
  ['#1F3D2B', '#002B1A'],
  ['#3D2B2B', '#2B1A1A'],
  ['#2B3D1F', '#1A2B00'],
];

function getGradient(name: string): [string, string] {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i);
    hash |= 0;
  }
  return GRADIENTS[Math.abs(hash) % GRADIENTS.length];
}

function formatPrice(item: MenuItem): string | null {
  if (item.price_original) return item.price_original;
  if (item.price != null) return `${item.currency ?? '$'}${item.price.toFixed(2)}`;
  return null;
}

interface DishCardProps {
  item: MenuItem;
  isRecommended: boolean;
  restaurantName?: string;
  showTranslation?: boolean;
}

type NavProp = StackNavigationProp<RootStackParamList, 'Restaurant'>;

export default function DishCard({
  item,
  isRecommended,
  restaurantName,
  showTranslation = false,
}: DishCardProps) {
  const navigation = useNavigation<NavProp>();
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  const displayName =
    showTranslation && item.name_translated ? item.name_translated : item.name;
  const price = formatPrice(item);
  const [gradStart, gradEnd] = getGradient(item.name);

  useEffect(() => {
    let cancelled = false;
    getDishImage(item.name, restaurantName).then((data) => {
      if (!cancelled && data.image_url) setImageUrl(data.image_url);
    });
    return () => { cancelled = true; };
  }, [item.name, restaurantName]);

  return (
    <TouchableOpacity
      onPress={() => navigation.navigate('DishDetail', { dishName: item.name })}
      activeOpacity={0.85}
      style={styles.card}
    >
      {/* Image area — 4:3 */}
      <View style={styles.imageWrap}>
        <LinearGradient
          colors={[gradStart, gradEnd]}
          style={StyleSheet.absoluteFill}
        />
        {/* Initial letter placeholder */}
        <Text style={styles.letterPlaceholder}>
          {item.name.charAt(0).toUpperCase()}
        </Text>
        {imageUrl && (
          <Image
            source={{ uri: imageUrl }}
            style={styles.image}
            resizeMode="cover"
          />
        )}
        {isRecommended && (
          <View style={styles.starBadge}>
            <Text style={styles.starText}>★</Text>
          </View>
        )}
      </View>

      {/* Info */}
      <View style={styles.info}>
        <Text style={styles.name} numberOfLines={2}>
          {isRecommended && <Text style={styles.starInline}>★ </Text>}
          {displayName}
        </Text>
        {price && <Text style={styles.price}>{price}</Text>}
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.card,
    borderRadius: Radius.md,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Colors.border,
    flex: 1,
    margin: Spacing.xs,
    // Shadow
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 3,
  },
  imageWrap: {
    aspectRatio: 4 / 3,
    width: '100%',
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  image: {
    ...StyleSheet.absoluteFillObject,
  },
  letterPlaceholder: {
    fontSize: 36,
    fontWeight: '300',
    color: Colors.primary + '44',
  },
  starBadge: {
    position: 'absolute',
    top: Spacing.xs,
    right: Spacing.xs,
    backgroundColor: Colors.primary,
    borderRadius: Radius.sm,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  starText: {
    fontSize: 10,
    color: Colors.bg,
    fontWeight: '700',
  },
  info: {
    padding: Spacing.sm,
    gap: 2,
  },
  name: {
    ...Typography.caption,
    color: Colors.textPrimary,
    fontWeight: '500',
    fontSize: 13,
  },
  starInline: {
    color: Colors.primary,
  },
  price: {
    ...Typography.price,
  },
});
