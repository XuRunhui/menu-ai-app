import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '@/navigation/AppNavigator';
import EntryCard from '@/components/EntryCard';
import { Colors, Spacing, Typography } from '@/theme';

type NavProp = StackNavigationProp<RootStackParamList, 'SearchMode'>;

export default function SearchModeScreen({ navigation }: { navigation: NavProp }) {
  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" backgroundColor={Colors.bg} />

      {/* Header row */}
      <View style={styles.headerRow}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backArrow}>←</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.content}>
        <Text style={styles.eyebrow}>SEARCH RESTAURANT</Text>
        <Text style={styles.title}>How would you like{'\n'}to explore the menu?</Text>
        <Text style={styles.subtitle}>
          Upload the physical menu image or let us fetch dishes automatically from reviews.
        </Text>

        <View style={styles.cards}>
          <EntryCard
            icon={<Text style={styles.emoji}>📷</Text>}
            title="Upload Menu Image"
            description="Take a photo of the menu at this restaurant for full dish details."
            onPress={() => navigation.navigate('Upload')}
          />
          <EntryCard
            icon={<Text style={styles.emoji}>🌐</Text>}
            title="Auto Fetch Menu"
            description="We'll search Google Places and web reviews to find popular dishes automatically."
            onPress={() => navigation.navigate('PlaceSearch')}
          />
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: Colors.bg,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.sm,
    height: 52,
  },
  backBtn: {
    padding: Spacing.sm,
    marginLeft: -Spacing.sm,
  },
  backArrow: {
    fontSize: 22,
    color: Colors.textPrimary,
  },
  content: {
    flex: 1,
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.lg,
  },
  eyebrow: {
    ...Typography.label,
    color: Colors.primary,
    marginBottom: Spacing.sm,
  },
  title: {
    ...Typography.h1,
    fontSize: 30,
    marginBottom: Spacing.md,
  },
  subtitle: {
    ...Typography.bodySecondary,
    marginBottom: Spacing.xl,
  },
  cards: {
    gap: 0,
  },
  emoji: {
    fontSize: 22,
  },
});
