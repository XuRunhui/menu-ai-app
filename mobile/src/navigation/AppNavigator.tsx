import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import { Colors } from '@/theme';

import HomeScreen from '@/screens/HomeScreen';
import SearchModeScreen from '@/screens/SearchModeScreen';
import UploadScreen from '@/screens/UploadScreen';
import PlaceSearchScreen from '@/screens/PlaceSearchScreen';
import RestaurantScreen from '@/screens/RestaurantScreen';
import DishDetailScreen from '@/screens/DishDetailScreen';

export type RootStackParamList = {
  Home: undefined;
  SearchMode: undefined;
  Upload: undefined;
  PlaceSearch: undefined;
  Restaurant: undefined;
  DishDetail: { dishName: string };
};

const Stack = createStackNavigator<RootStackParamList>();

export default function AppNavigator() {
  return (
    <Stack.Navigator
      initialRouteName="Home"
      screenOptions={{
        headerShown: false,
        cardStyle: { backgroundColor: Colors.bg },
        gestureEnabled: true,
        // Smooth horizontal slide transition
        cardStyleInterpolator: ({ current, layouts }) => ({
          cardStyle: {
            transform: [
              {
                translateX: current.progress.interpolate({
                  inputRange: [0, 1],
                  outputRange: [layouts.screen.width, 0],
                }),
              },
            ],
          },
        }),
      }}
    >
      <Stack.Screen name="Home" component={HomeScreen} />
      <Stack.Screen name="SearchMode" component={SearchModeScreen} />
      <Stack.Screen name="Upload" component={UploadScreen} />
      <Stack.Screen name="PlaceSearch" component={PlaceSearchScreen} />
      <Stack.Screen name="Restaurant" component={RestaurantScreen} />
      <Stack.Screen name="DishDetail" component={DishDetailScreen} />
    </Stack.Navigator>
  );
}
