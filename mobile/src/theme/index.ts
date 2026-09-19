import { TextStyle } from 'react-native';

export const Colors = {
  bg: '#0F0F0F',
  card: '#1A1A1A',
  surface: '#252525',
  primary: '#C9A96E',
  primaryDim: '#C9A96E22',
  textPrimary: '#F5F5F5',
  textSecondary: '#8A8A8A',
  border: '#2A2A2A',
  danger: '#E05252',
  success: '#52C095',
  overlay: 'rgba(0,0,0,0.6)',
} as const;

export const Radius = {
  sm: 8,
  md: 12,
  lg: 20,
  xl: 28,
} as const;

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 40,
} as const;

export const Typography: Record<string, TextStyle> = {
  h1: {
    fontSize: 36,
    fontWeight: '700',
    color: Colors.textPrimary,
    letterSpacing: -0.5,
  },
  h2: {
    fontSize: 22,
    fontWeight: '600',
    color: Colors.textPrimary,
    letterSpacing: -0.3,
  },
  h3: {
    fontSize: 17,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
  body: {
    fontSize: 15,
    color: Colors.textPrimary,
    lineHeight: 22,
  },
  bodySecondary: {
    fontSize: 14,
    color: Colors.textSecondary,
    lineHeight: 20,
  },
  caption: {
    fontSize: 12,
    color: Colors.textSecondary,
    lineHeight: 16,
  },
  label: {
    fontSize: 11,
    fontWeight: '600',
    color: Colors.textSecondary,
    letterSpacing: 1.4,
    textTransform: 'uppercase',
  },
  price: {
    fontSize: 13,
    fontWeight: '500',
    color: Colors.primary,
  },
};
