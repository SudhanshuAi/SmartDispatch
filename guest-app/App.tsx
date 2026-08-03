import { StatusBar } from "expo-status-bar";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { AuthProvider, useAuth } from "./src/auth/AuthContext";
import { HomeScreen } from "./src/screens/HomeScreen";
import { LoginScreen } from "./src/screens/LoginScreen";

function Root() {
  const { user, ready } = useAuth();
  if (!ready) {
    return (
      <View style={styles.boot}>
        <ActivityIndicator color="#2bb3a3" size="large" />
      </View>
    );
  }
  return user ? <HomeScreen /> : <LoginScreen />;
}

export default function App() {
  return (
    <AuthProvider>
      <StatusBar style="light" />
      <Root />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    backgroundColor: "#0f3d38",
    alignItems: "center",
    justifyContent: "center",
  },
});
