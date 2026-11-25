import { useRef, useState } from 'react';
import { Alert, Image, Pressable, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { useOpsBridgeMobileAuth } from '../src/auth';

const API = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8080/api/v1';
type UploadAsset = { uri: string; name: string; mimeType?: string };

export default function Home() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [caseId, setCaseId] = useState('');
  const [asset, setAsset] = useState<UploadAsset | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const camera = useRef<CameraView>(null);
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const auth = useOpsBridgeMobileAuth();

  async function createCase() {
    try {
      if (auth.identityConfigured && !auth.accessToken) {
        Alert.alert('Sign in required', 'Sign in with your organization before starting a case.');
        return;
      }
      const response = await fetch(`${API}/cases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...await auth.headers() },
        body: JSON.stringify({ workerName: name, email, role: 'Field Operations Associate', country: 'IN' }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Unable to create case');
      setCaseId(result.id);
      Alert.alert('Case started', `Reference ${result.id}`);
    } catch (error) {
      Alert.alert('Connection issue', error instanceof Error ? error.message : 'Service unavailable');
    }
  }

  async function chooseDocument() {
    const result = await DocumentPicker.getDocumentAsync({
      copyToCacheDirectory: true,
      type: ['application/pdf', 'image/png', 'image/jpeg', 'text/plain'],
    });
    if (!result.canceled) {
      const selected = result.assets[0];
      setAsset({ uri: selected.uri, name: selected.name, mimeType: selected.mimeType ?? undefined });
    }
  }

  async function openCamera() {
    if (!cameraPermission?.granted) {
      const permission = await requestCameraPermission();
      if (!permission.granted) return Alert.alert('Camera permission needed', 'Allow camera access to capture a document image.');
    }
    setCameraOpen(true);
  }

  async function captureDocument() {
    try {
      const photo = await camera.current?.takePictureAsync({ quality: 0.85 });
      if (photo?.uri) {
        setAsset({ uri: photo.uri, name: `document-${Date.now()}.jpg`, mimeType: 'image/jpeg' });
        setCameraOpen(false);
      }
    } catch (error) {
      Alert.alert('Camera issue', error instanceof Error ? error.message : 'Could not capture the image');
    }
  }

  async function uploadDocument() {
    if (!caseId || !asset) return Alert.alert('Choose a case and document', 'Start the case and select or capture a document first.');
    try {
      const body = new FormData();
      body.append('file', { uri: asset.uri, name: asset.name, type: asset.mimeType ?? 'application/octet-stream' } as any);
      body.append('documentType', 'identity');
      const response = await fetch(`${API}/cases/${encodeURIComponent(caseId)}/documents`, {
        method: 'POST', headers: await auth.headers(), body,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error ?? 'Unable to upload document');
      Alert.alert('Document queued', 'The document is ready for secure processing.');
    } catch (error) {
      Alert.alert('Upload issue', error instanceof Error ? error.message : 'Service unavailable');
    }
  }

  return <SafeAreaView style={styles.safe}><ScrollView contentContainerStyle={styles.page}>
    <Text style={styles.brand}>◈ OPSBRIDGE</Text>
    <Text style={styles.eyebrow}>FIELD OPERATIONS</Text>
    <Text style={styles.title}>Worker check-in</Text>
    <Text style={styles.body}>Start onboarding, select an existing file, or capture a document image on device.</Text>
    {auth.identityConfigured && <View style={styles.card}>
      <Text style={styles.label}>Organization access</Text>
      <Pressable style={styles.secondary} disabled={!auth.request} onPress={() => void auth.signIn()}><Text style={styles.secondaryText}>{auth.accessToken ? 'Signed in' : 'Sign in securely'}</Text></Pressable>
      {auth.accessToken && <Pressable style={styles.secondary} onPress={() => void auth.logout()}><Text style={styles.secondaryText}>Sign out</Text></Pressable>}
    </View>}
    <View style={styles.card}>
      <Text style={styles.label}>Worker name</Text><TextInput style={styles.input} value={name} onChangeText={setName} placeholder="Full name" />
      <Text style={styles.label}>Email address</Text><TextInput style={styles.input} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder="worker@example.com" />
      <Pressable style={styles.primary} onPress={createCase}><Text style={styles.primaryText}>Create onboarding case</Text></Pressable>
      {caseId !== '' && <Text style={styles.success}>Active reference: {caseId}</Text>}
    </View>
    <View style={styles.card}>
      <Text style={styles.label}>Supporting document</Text>
      <Text style={styles.body}>{asset?.name ?? 'No document selected'}</Text>
      <Pressable style={styles.secondary} onPress={chooseDocument}><Text style={styles.secondaryText}>Choose a file</Text></Pressable>
      <Pressable style={styles.secondary} onPress={() => void openCamera()}><Text style={styles.secondaryText}>Capture with camera</Text></Pressable>
      {cameraOpen && <View style={styles.cameraWrap}>
        <CameraView ref={camera} style={styles.camera} facing="back" />
        <Pressable style={styles.primary} onPress={captureDocument}><Text style={styles.primaryText}>Take document photo</Text></Pressable>
      </View>}
      {asset && <Image source={{ uri: asset.uri }} style={styles.preview} resizeMode="cover" />}
      {asset && <Pressable style={styles.primary} onPress={uploadDocument}><Text style={styles.primaryText}>Upload to this case</Text></Pressable>}
    </View>
    <Text style={styles.foot}>Use synthetic information in this portfolio environment.</Text>
  </ScrollView></SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f4f8f5' }, page: { padding: 24, paddingTop: 32 },
  brand: { fontSize: 15, fontWeight: '800', color: '#173a31', marginBottom: 40 },
  eyebrow: { fontSize: 10, letterSpacing: 2, color: '#648272' }, title: { fontSize: 27, fontWeight: '800', color: '#1a3028', marginTop: 8 },
  body: { fontSize: 13, color: '#718078', lineHeight: 20, marginTop: 7, marginBottom: 14 },
  card: { backgroundColor: 'white', borderColor: '#e4ebe6', borderWidth: 1, borderRadius: 12, padding: 18, marginBottom: 13 },
  label: { fontSize: 12, fontWeight: '700', color: '#41584d', marginBottom: 7, marginTop: 7 },
  input: { height: 43, borderWidth: 1, borderColor: '#dce5df', borderRadius: 7, paddingHorizontal: 11, marginBottom: 8 },
  primary: { backgroundColor: '#183e33', padding: 13, borderRadius: 7, alignItems: 'center', marginTop: 8 },
  primaryText: { color: '#e4ffd2', fontWeight: '700', fontSize: 13 }, secondary: { borderWidth: 1, borderColor: '#dbe4de', padding: 12, borderRadius: 7, alignItems: 'center', marginTop: 8 },
  secondaryText: { color: '#315d48', fontWeight: '700' }, success: { color: '#347349', fontSize: 11, marginTop: 10 },
  cameraWrap: { height: 320, marginTop: 12 }, camera: { flex: 1, borderRadius: 8 }, preview: { height: 190, marginTop: 12, borderRadius: 8 },
  foot: { fontSize: 10, color: '#8a9890', textAlign: 'center', marginTop: 12 },
});
