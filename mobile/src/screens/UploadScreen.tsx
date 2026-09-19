import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Image,
  StyleSheet,
  Alert,
  StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as ImagePicker from 'expo-image-picker';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '@/navigation/AppNavigator';
import { parseMenu } from '@/api/client';
import { useAppContext } from '@/store/AppContext';
import LoadingOverlay from '@/components/LoadingOverlay';
import { Colors, Radius, Spacing, Typography } from '@/theme';

type NavProp = StackNavigationProp<RootStackParamList, 'Upload'>;

const LANGUAGES = [
  { code: null, label: 'No Translation' },
  { code: 'English', label: 'English' },
  { code: 'Chinese', label: '中文' },
  { code: 'Japanese', label: '日本語' },
  { code: 'Korean', label: '한국어' },
  { code: 'Spanish', label: 'Español' },
  { code: 'French', label: 'Français' },
  { code: 'German', label: 'Deutsch' },
  { code: 'Italian', label: 'Italiano' },
  { code: 'Portuguese', label: 'Português' },
  { code: 'Arabic', label: 'العربية' },
];

export default function UploadScreen({ navigation }: { navigation: NavProp }) {
  const { setParsedMenu, setRestaurant } = useAppContext();

  const [imageUri, setImageUri] = useState<string | null>(null);
  const [restaurantName, setRestaurantName] = useState('');
  const [selectedLang, setSelectedLang] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pickImage = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission required', 'Please allow photo access to upload menu images.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.85,
      allowsEditing: false,
    });
    if (!result.canceled && result.assets[0]) {
      setImageUri(result.assets[0].uri);
      setError(null);
    }
  };

  const handleParse = async () => {
    if (!imageUri) {
      setError('Please select a menu image first.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await parseMenu(imageUri, selectedLang);
      setParsedMenu(result, selectedLang);
      if (restaurantName.trim()) {
        setRestaurant({ place_id: '', name: restaurantName.trim(), location: '' });
      }
      navigation.navigate('Restaurant');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to parse menu. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" backgroundColor={Colors.bg} />

      {/* Header */}
      <View style={styles.headerRow}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backArrow}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Upload Menu</Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.eyebrow}>MENU IMAGE</Text>
        <Text style={styles.title}>Upload a menu image</Text>
        <Text style={styles.subtitle}>
          Take a photo of any restaurant menu — we'll parse it instantly.
        </Text>

        {/* Image picker zone */}
        <TouchableOpacity onPress={pickImage} activeOpacity={0.8} style={styles.dropZone}>
          {imageUri ? (
            <>
              <Image source={{ uri: imageUri }} style={styles.preview} resizeMode="cover" />
              <TouchableOpacity
                onPress={() => setImageUri(null)}
                style={styles.clearBtn}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              >
                <Text style={styles.clearText}>✕</Text>
              </TouchableOpacity>
            </>
          ) : (
            <View style={styles.dropZoneInner}>
              <Text style={styles.dropIcon}>📷</Text>
              <Text style={styles.dropLabel}>Tap to choose a photo</Text>
              <Text style={styles.dropHint}>JPG, PNG, HEIC supported</Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Restaurant name */}
        <Text style={styles.fieldLabel}>Restaurant name (optional)</Text>
        <View style={styles.inputWrap}>
          <Text style={styles.inputIcon}>🏪</Text>
          <TextInput
            style={styles.input}
            value={restaurantName}
            onChangeText={setRestaurantName}
            placeholder="e.g. BCD Tofu House"
            placeholderTextColor={Colors.textSecondary + '88'}
          />
        </View>
        <Text style={styles.fieldHint}>Helps find dish photos and enables AI insights.</Text>

        {/* Language selector */}
        <Text style={styles.fieldLabel}>Translate to (optional)</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.langRow}
        >
          {LANGUAGES.map((lang) => {
            const active = selectedLang === lang.code;
            return (
              <TouchableOpacity
                key={lang.code ?? 'none'}
                onPress={() => setSelectedLang(lang.code)}
                activeOpacity={0.7}
                style={[styles.langPill, active && styles.langPillActive]}
              >
                <Text style={[styles.langText, active && styles.langTextActive]}>
                  {lang.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
        <Text style={styles.fieldHint}>Language is detected automatically from the image.</Text>

        {/* Error */}
        {error && <Text style={styles.error}>{error}</Text>}

        {/* CTA */}
        <TouchableOpacity
          onPress={handleParse}
          activeOpacity={0.8}
          style={[styles.cta, !imageUri && styles.ctaDisabled]}
          disabled={!imageUri || loading}
        >
          <Text style={styles.ctaText}>Parse Menu</Text>
        </TouchableOpacity>
      </ScrollView>

      {loading && <LoadingOverlay message="Analysing menu…" />}
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
  scroll: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.xl, gap: Spacing.sm },
  eyebrow: { ...Typography.label, color: Colors.primary, marginTop: Spacing.md },
  title: { ...Typography.h2 },
  subtitle: { ...Typography.bodySecondary },
  dropZone: {
    height: 200,
    borderRadius: Radius.lg,
    borderWidth: 2,
    borderColor: Colors.border,
    borderStyle: 'dashed',
    overflow: 'hidden',
    backgroundColor: Colors.card,
    marginTop: Spacing.sm,
    marginBottom: Spacing.md,
  },
  dropZoneInner: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
  },
  dropIcon: { fontSize: 36 },
  dropLabel: { ...Typography.body, fontWeight: '500' },
  dropHint: { ...Typography.caption },
  preview: { flex: 1 },
  clearBtn: {
    position: 'absolute',
    top: Spacing.sm,
    right: Spacing.sm,
    backgroundColor: Colors.overlay,
    borderRadius: 999,
    width: 28,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  clearText: { color: Colors.textPrimary, fontSize: 13, fontWeight: '600' },
  fieldLabel: { ...Typography.label, color: Colors.textSecondary, marginTop: Spacing.sm },
  fieldHint: { ...Typography.caption, marginTop: 2, marginBottom: Spacing.sm },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.sm,
    height: 44,
    marginTop: 4,
  },
  inputIcon: { fontSize: 16, marginRight: Spacing.sm },
  input: {
    flex: 1,
    ...Typography.body,
    color: Colors.textPrimary,
  },
  langRow: {
    gap: Spacing.sm,
    paddingVertical: Spacing.xs,
    marginTop: 4,
  },
  langPill: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  langPillActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  langText: { ...Typography.caption, fontWeight: '500', color: Colors.textSecondary },
  langTextActive: { color: Colors.bg, fontWeight: '700' },
  error: {
    ...Typography.caption,
    color: Colors.danger,
    backgroundColor: Colors.danger + '18',
    padding: Spacing.sm,
    borderRadius: Radius.sm,
    marginTop: Spacing.sm,
  },
  cta: {
    backgroundColor: Colors.primary,
    borderRadius: Radius.md,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: Spacing.lg,
  },
  ctaDisabled: { opacity: 0.4 },
  ctaText: { fontSize: 16, fontWeight: '700', color: Colors.bg },
});
