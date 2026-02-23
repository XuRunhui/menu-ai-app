import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  StatusBar,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RouteProp } from '@react-navigation/native';
import type { RootStackParamList } from '@/navigation/AppNavigator';
import { getDishContext, getDishImage } from '@/api/client';
import { useAppContext } from '@/store/AppContext';
import { Colors, Radius, Spacing, Typography } from '@/theme';
import type { DishContextResponse } from '@/types';

type NavProp = StackNavigationProp<RootStackParamList, 'DishDetail'>;
type RoutePropType = RouteProp<RootStackParamList, 'DishDetail'>;

const { width: SCREEN_W } = Dimensions.get('window');
const HERO_HEIGHT = SCREEN_W * 0.65;

function Tag({ label, variant }: { label: string; variant: 'gold' | 'outline' }) {
  return (
    <View style={variant === 'gold' ? tagStyles.gold : tagStyles.outline}>
      <Text style={variant === 'gold' ? tagStyles.goldText : tagStyles.outlineText}>
        {label}
      </Text>
    </View>
  );
}

const tagStyles = StyleSheet.create({
  gold: {
    backgroundColor: Colors.primaryDim,
    borderRadius: Radius.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: Colors.primary + '55',
  },
  goldText: { ...Typography.caption, color: Colors.primary, fontWeight: '600' },
  outline: {
    borderRadius: Radius.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  outlineText: { ...Typography.caption, color: Colors.textSecondary },
});

export default function DishDetailScreen({
  navigation,
  route,
}: {
  navigation: NavProp;
  route: RoutePropType;
}) {
  const { dishName } = route.params;
  const { restaurant, knowledgeBaseStatus, parsedMenu } = useAppContext();

  const [context, setContext] = useState<DishContextResponse | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [loadingContext, setLoadingContext] = useState(false);
  const [loadingImage, setLoadingImage] = useState(true);

  // Find dish in parsedMenu for fallback description
  const menuItem = parsedMenu?.menu
    .flatMap((c) => c.items)
    .find((i) => i.name === dishName);

  // Fetch dish image
  useEffect(() => {
    let cancelled = false;
    getDishImage(dishName, restaurant?.name).then((data) => {
      if (!cancelled && data.image_url) setImageUrl(data.image_url);
      setLoadingImage(false);
    }).catch(() => setLoadingImage(false));
    return () => { cancelled = true; };
  }, [dishName, restaurant?.name]);

  // Fetch AI context if restaurant is available
  useEffect(() => {
    if (!restaurant?.name || knowledgeBaseStatus === 'idle') return;
    let cancelled = false;
    setLoadingContext(true);
    getDishContext(dishName, restaurant.name, restaurant.location)
      .then((data) => { if (!cancelled) setContext(data); })
      .catch(() => {}) // graceful fallback
      .finally(() => { if (!cancelled) setLoadingContext(false); });
    return () => { cancelled = true; };
  }, [dishName, restaurant, knowledgeBaseStatus]);

  const tasteTexture = context?.taste_texture?.round2;
  const description = context?.menu_description ?? menuItem?.description ?? null;
  const flavorProfile = tasteTexture?.flavor_profile;
  const excerpts = context?.review_excerpts?.slice(0, 3) ?? [];
  const price = context?.metadata.price ?? menuItem?.price;
  const currency = menuItem?.currency ?? '$';
  const spicyLevel = context?.metadata.spicy_level ?? menuItem?.spicy_level ?? 0;
  const dietaryTags = [
    ...(context?.metadata.dietary_tags ?? menuItem?.dietary_tags ?? []),
    ...(context?.metadata.allergens ?? menuItem?.allergens ?? []),
  ];

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <StatusBar barStyle="light-content" backgroundColor="transparent" translucent />
      <ScrollView showsVerticalScrollIndicator={false} bounces>
        {/* Hero image */}
        <View style={styles.hero}>
          <LinearGradient
            colors={['#2A1A0F', '#0F0A05']}
            style={StyleSheet.absoluteFill}
          />
          {loadingImage && (
            <ActivityIndicator color={Colors.primary} style={styles.heroLoader} />
          )}
          {imageUrl && (
            <Image
              source={{ uri: imageUrl }}
              style={styles.heroImage}
              resizeMode="cover"
              onLoad={() => setLoadingImage(false)}
            />
          )}
          <LinearGradient
            colors={['transparent', Colors.bg]}
            style={styles.heroGradient}
          />
          {/* Back button */}
          <TouchableOpacity
            onPress={() => navigation.goBack()}
            style={styles.heroBack}
          >
            <Text style={styles.heroBackText}>←</Text>
          </TouchableOpacity>
          {/* Dish name over hero */}
          <View style={styles.heroTitle}>
            <Text style={styles.dishName}>{dishName}</Text>
            {context?.is_popular && (
              <View style={styles.popularBadge}>
                <Text style={styles.popularText}>★ Popular</Text>
              </View>
            )}
          </View>
        </View>

        {/* Content */}
        <View style={styles.content}>

          {/* Loading context skeleton */}
          {loadingContext && (
            <View style={styles.skeletonWrap}>
              <ActivityIndicator color={Colors.primary} />
              <Text style={styles.skeletonText}>Loading AI insights…</Text>
            </View>
          )}

          {/* Description / flavor profile */}
          {(description || flavorProfile) && !loadingContext && (
            <View style={styles.section}>
              <Text style={styles.sectionLabel}>ABOUT THIS DISH</Text>
              {flavorProfile && (
                <Text style={styles.flavorQuote}>"{flavorProfile}"</Text>
              )}
              {description && (
                <Text style={styles.description}>{description}</Text>
              )}
            </View>
          )}

          {/* Taste & texture tags */}
          {tasteTexture && (tasteTexture.tastes.length > 0 || tasteTexture.textures.length > 0) && (
            <View style={styles.section}>
              <Text style={styles.sectionLabel}>FLAVOUR PROFILE</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tagRow}>
                {tasteTexture.tastes.map((t) => <Tag key={t} label={t} variant="gold" />)}
                {tasteTexture.textures.map((t) => <Tag key={t} label={t} variant="outline" />)}
              </ScrollView>
            </View>
          )}

          {/* Metadata row */}
          {(price != null || (spicyLevel && spicyLevel > 0) || dietaryTags.length > 0) && (
            <View style={styles.metaRow}>
              {price != null && (
                <View style={styles.metaChip}>
                  <Text style={styles.metaChipText}>{currency}{typeof price === 'number' ? price.toFixed(2) : price}</Text>
                </View>
              )}
              {spicyLevel && spicyLevel > 0 ? (
                <View style={styles.metaChip}>
                  <Text style={styles.metaChipText}>{'🌶'.repeat(Math.min(spicyLevel, 5))}</Text>
                </View>
              ) : null}
              {dietaryTags.slice(0, 3).map((tag) => (
                <View key={tag} style={styles.metaChip}>
                  <Text style={styles.metaChipText}>{tag}</Text>
                </View>
              ))}
            </View>
          )}

          {/* Review excerpts */}
          {excerpts.length > 0 && (
            <View style={styles.section}>
              <Text style={styles.sectionLabel}>FROM THE REVIEWS</Text>
              {excerpts.map((excerpt, i) => (
                <View key={i} style={styles.quoteBlock}>
                  <Text style={styles.quoteText}>"{excerpt}"</Text>
                </View>
              ))}
            </View>
          )}

          {/* Fallback: no AI context */}
          {!loadingContext && !context && !description && (
            <View style={styles.section}>
              <Text style={styles.noContextText}>
                Search this restaurant via Auto Fetch to unlock AI insights and review summaries.
              </Text>
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  hero: {
    height: HERO_HEIGHT,
    width: '100%',
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroLoader: { position: 'absolute' },
  heroImage: { ...StyleSheet.absoluteFillObject },
  heroGradient: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: HERO_HEIGHT * 0.55,
  },
  heroBack: {
    position: 'absolute',
    top: 52,
    left: Spacing.md,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.overlay,
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroBackText: { fontSize: 20, color: Colors.textPrimary },
  heroTitle: {
    position: 'absolute',
    bottom: Spacing.lg,
    left: Spacing.md,
    right: Spacing.md,
  },
  dishName: {
    fontSize: 28,
    fontWeight: '700',
    color: Colors.textPrimary,
    letterSpacing: -0.5,
    textShadowColor: 'rgba(0,0,0,0.6)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },
  popularBadge: {
    marginTop: Spacing.xs,
    alignSelf: 'flex-start',
    backgroundColor: Colors.primary,
    borderRadius: Radius.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
  },
  popularText: { ...Typography.caption, color: Colors.bg, fontWeight: '700' },
  content: { padding: Spacing.md, gap: Spacing.lg },
  skeletonWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    padding: Spacing.md,
    backgroundColor: Colors.card,
    borderRadius: Radius.md,
  },
  skeletonText: { ...Typography.bodySecondary },
  section: { gap: Spacing.sm },
  sectionLabel: { ...Typography.label, color: Colors.primary },
  flavorQuote: {
    ...Typography.body,
    color: Colors.textSecondary,
    fontStyle: 'italic',
    lineHeight: 24,
  },
  description: { ...Typography.body, lineHeight: 24 },
  tagRow: { gap: Spacing.sm, paddingVertical: Spacing.xs },
  metaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  metaChip: {
    backgroundColor: Colors.surface,
    borderRadius: Radius.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  metaChipText: { ...Typography.caption, color: Colors.textPrimary },
  quoteBlock: {
    borderLeftWidth: 2,
    borderLeftColor: Colors.primary,
    paddingLeft: Spacing.md,
    paddingVertical: Spacing.xs,
  },
  quoteText: { ...Typography.bodySecondary, fontStyle: 'italic', lineHeight: 21 },
  noContextText: { ...Typography.bodySecondary, lineHeight: 22 },
});
