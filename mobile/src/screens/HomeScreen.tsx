import React from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '@/navigation/AppNavigator';
import EntryCard from '@/components/EntryCard';
import { Colors, Spacing, Typography } from '@/theme';

type NavProp = StackNavigationProp<RootStackParamList, 'Home'>;

export default function HomeScreen({ navigation }: { navigation: NavProp }) {
  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" backgroundColor={Colors.bg} />
      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.eyebrow}>AI-POWERED DINING GUIDE</Text>
          <Text style={styles.title}>Menuist</Text>
          <Text style={styles.subtitle}>
            Parse any menu, discover dishes, and get personalized recommendations.
          </Text>
        </View>

        {/* Entry cards */}
        <View style={styles.cards}>
          <EntryCard
            icon={<Text style={styles.emoji}>📷</Text>}
            title="Upload Menu"
            description="Photograph any menu and get instant AI parsing with translation in 12+ languages."
            onPress={() => navigation.navigate('Upload')}
          />
          <EntryCard
            icon={<Text style={styles.emoji}>📍</Text>}
            title="Search Restaurant"
            description="Find a restaurant by name to explore its menu and popular dishes from reviews."
            onPress={() => navigation.navigate('SearchMode')}
          />
          <EntryCard
            icon={<Text style={styles.emoji}>✨</Text>}
            title="AI Assistant"
            description="Get a personalized dining experience powered by conversational AI recommendations."
            disabled
          />
        </View>

        <Text style={styles.footer}>
          Powered by DeepSeek Vision · Google Places · RAG
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: Colors.bg,
  },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.xl,
  },
  header: {
    alignItems: 'center',
    marginBottom: Spacing.xl,
  },
  eyebrow: {
    ...Typography.label,
    color: Colors.primary,
    marginBottom: Spacing.sm,
    textAlign: 'center',
  },
  title: {
    fontSize: 52,
    fontWeight: '700',
    color: Colors.textPrimary,
    letterSpacing: -1.5,
    marginBottom: Spacing.sm,
  },
  subtitle: {
    ...Typography.bodySecondary,
    textAlign: 'center',
    maxWidth: 300,
  },
  cards: {
    gap: 0,
  },
  emoji: {
    fontSize: 22,
  },
  footer: {
    ...Typography.caption,
    textAlign: 'center',
    marginTop: Spacing.xl,
    color: Colors.textSecondary + '88',
  },
});
