import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '@/navigation/AppNavigator';
import { searchPlaces, getPlaceDetails, buildKnowledgeBase } from '@/api/client';
import { useAppContext } from '@/store/AppContext';
import { Colors, Radius, Spacing, Typography } from '@/theme';
import type { GooglePlace } from '@/types';

type NavProp = StackNavigationProp<RootStackParamList, 'PlaceSearch'>;

export default function PlaceSearchScreen({ navigation }: { navigation: NavProp }) {
  const { setPlaceDetails, setRestaurant, setKnowledgeBaseStatus } = useAppContext();

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GooglePlace[]>([]);
  const [searching, setSearching] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const inputRef = useRef<TextInput>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSearchError(null);
    try {
      const data = await searchPlaces(query.trim());
      setResults(data.results ?? []);
    } catch (e) {
      setSearchError('Search failed. Check your connection and try again.');
    } finally {
      setSearching(false);
    }
  };

  const handleSelect = async (place: GooglePlace) => {
    setSelecting(true);
    try {
      const details = await getPlaceDetails(place.place_id);
      setPlaceDetails(details);
      setRestaurant({
        place_id: details.place.place_id,
        name: details.place.name,
        location: details.place.formatted_address ?? '',
        rating: details.place.rating,
        photo_urls: details.place.photo_urls ?? [],
      });
      // Fire-and-forget knowledge base build
      setKnowledgeBaseStatus('building');
      buildKnowledgeBase(
        details.place.name,
        details.place.formatted_address ?? '',
        details.place.place_id,
      )
        .then(() => setKnowledgeBaseStatus('ready'))
        .catch(() => setKnowledgeBaseStatus('error'));

      navigation.navigate('Restaurant');
    } catch (e) {
      setSearchError('Failed to load restaurant details. Please try again.');
    } finally {
      setSelecting(false);
    }
  };

  const renderItem = ({ item }: { item: GooglePlace }) => (
    <TouchableOpacity
      onPress={() => handleSelect(item)}
      activeOpacity={0.75}
      style={styles.resultCard}
    >
      <View style={styles.resultInfo}>
        <Text style={styles.resultName} numberOfLines={1}>{item.name}</Text>
        {item.formatted_address && (
          <Text style={styles.resultAddress} numberOfLines={1}>{item.formatted_address}</Text>
        )}
      </View>
      {item.rating != null && (
        <View style={styles.ratingWrap}>
          <Text style={styles.ratingStar}>★</Text>
          <Text style={styles.ratingText}>{item.rating.toFixed(1)}</Text>
        </View>
      )}
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" backgroundColor={Colors.bg} />

      {/* Header */}
      <View style={styles.headerRow}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backArrow}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Search Restaurant</Text>
      </View>

      {/* Search bar */}
      <View style={styles.searchRow}>
        <View style={styles.searchBox}>
          <Text style={styles.searchIcon}>🔍</Text>
          <TextInput
            ref={inputRef}
            style={styles.searchInput}
            value={query}
            onChangeText={setQuery}
            placeholder="Restaurant name or address…"
            placeholderTextColor={Colors.textSecondary + '88'}
            returnKeyType="search"
            onSubmitEditing={handleSearch}
            autoFocus
          />
          {query.length > 0 && (
            <TouchableOpacity onPress={() => { setQuery(''); setResults([]); }}>
              <Text style={styles.clearText}>✕</Text>
            </TouchableOpacity>
          )}
        </View>
        <TouchableOpacity onPress={handleSearch} activeOpacity={0.8} style={styles.searchBtn}>
          <Text style={styles.searchBtnText}>Search</Text>
        </TouchableOpacity>
      </View>

      {/* Error */}
      {searchError && (
        <Text style={styles.error}>{searchError}</Text>
      )}

      {/* Results */}
      {searching || selecting ? (
        <View style={styles.loadingWrap}>
          <ActivityIndicator color={Colors.primary} size="large" />
          <Text style={styles.loadingText}>
            {selecting ? 'Loading restaurant…' : 'Searching…'}
          </Text>
        </View>
      ) : (
        <FlatList
          data={results}
          keyExtractor={(item) => item.place_id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          ListEmptyComponent={
            query.length > 0 && !searching ? (
              <Text style={styles.emptyText}>No results found. Try a different search term.</Text>
            ) : null
          }
          showsVerticalScrollIndicator={false}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.bg },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.sm,
    height: 52,
    gap: Spacing.sm,
  },
  backBtn: { padding: Spacing.sm, marginLeft: -Spacing.sm },
  backArrow: { fontSize: 22, color: Colors.textPrimary },
  headerTitle: { ...Typography.h3, color: Colors.textSecondary },
  searchRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    marginTop: Spacing.sm,
    marginBottom: Spacing.md,
  },
  searchBox: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.sm,
    height: 44,
    gap: Spacing.sm,
  },
  searchIcon: { fontSize: 15 },
  searchInput: {
    flex: 1,
    ...Typography.body,
    color: Colors.textPrimary,
  },
  clearText: { color: Colors.textSecondary, fontSize: 14, padding: 2 },
  searchBtn: {
    backgroundColor: Colors.primary,
    borderRadius: Radius.md,
    paddingHorizontal: Spacing.md,
    justifyContent: 'center',
    height: 44,
  },
  searchBtnText: { color: Colors.bg, fontWeight: '700', fontSize: 14 },
  error: {
    ...Typography.caption,
    color: Colors.danger,
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
  },
  loadingWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.md,
  },
  loadingText: { ...Typography.bodySecondary },
  listContent: {
    paddingHorizontal: Spacing.md,
    paddingBottom: Spacing.xl,
    gap: Spacing.sm,
  },
  resultCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.card,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
  },
  resultInfo: { flex: 1, gap: 3 },
  resultName: { ...Typography.body, fontWeight: '600' },
  resultAddress: { ...Typography.caption },
  ratingWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    marginLeft: Spacing.sm,
  },
  ratingStar: { color: Colors.primary, fontSize: 13 },
  ratingText: { ...Typography.caption, color: Colors.primary, fontWeight: '600' },
  emptyText: {
    ...Typography.bodySecondary,
    textAlign: 'center',
    marginTop: Spacing.xl,
  },
});
