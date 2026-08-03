import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useAuth } from "../auth/AuthContext";

export function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState("guest001@smartdispatch.local");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    setBusy(true);
    setError(null);
    try {
      await login(email);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.wrap}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.card}>
        <Text style={styles.brand}>
          Smart<Text style={styles.brandAccent}>Dispatch</Text>
        </Text>
        <Text style={styles.sub}>Guest pickup & ride tracking</Text>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Text style={styles.label}>Email</Text>
        <TextInput
          style={styles.input}
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
          placeholder="guest001@smartdispatch.local"
          placeholderTextColor="#8aa39d"
        />

        <Pressable style={[styles.btn, busy && styles.btnDisabled]} onPress={() => void onSubmit()} disabled={busy}>
          {busy ? <ActivityIndicator color="#06241f" /> : <Text style={styles.btnText}>Continue</Text>}
        </Pressable>

        <Text style={styles.hint}>Seed guest: guest001@smartdispatch.local (no password in stub auth)</Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: "#0f3d38",
    justifyContent: "center",
    padding: 24,
  },
  card: {
    backgroundColor: "#f7fbfa",
    borderRadius: 20,
    padding: 24,
    gap: 10,
  },
  brand: {
    fontSize: 34,
    fontWeight: "800",
    color: "#0f3d38",
    letterSpacing: 0.3,
  },
  brandAccent: { color: "#1f8a7d" },
  sub: { color: "#5a736e", marginBottom: 8 },
  label: { color: "#5a736e", fontSize: 13, fontWeight: "600" },
  input: {
    borderWidth: 1,
    borderColor: "#c9dbd6",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: "#0f3d38",
    backgroundColor: "#fff",
  },
  btn: {
    marginTop: 8,
    backgroundColor: "#2bb3a3",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  btnDisabled: { opacity: 0.7 },
  btnText: { color: "#06241f", fontWeight: "700", fontSize: 16 },
  error: {
    backgroundColor: "#fde8e8",
    color: "#a33",
    padding: 10,
    borderRadius: 10,
    overflow: "hidden",
  },
  hint: { color: "#8aa39d", fontSize: 12, marginTop: 4 },
});
