import { useEffect, useRef, useState } from 'react';
import * as AuthSession from 'expo-auth-session';
import * as SecureStore from 'expo-secure-store';
import * as WebBrowser from 'expo-web-browser';

WebBrowser.maybeCompleteAuthSession();

const issuer = process.env.EXPO_PUBLIC_OIDC_ISSUER ?? '';
const clientId = 'opsbridge-field';
const redirectUri = AuthSession.makeRedirectUri({ scheme: 'opsbridge', path: 'auth' });

export function useOpsBridgeMobileAuth() {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const exchangedCode = useRef<string | null>(null);
  const discovery = AuthSession.useAutoDiscovery(issuer || 'http://localhost:8081/realms/opsbridge');
  const [request, response, promptAsync] = AuthSession.useAuthRequest({
    clientId,
    redirectUri,
    responseType: AuthSession.ResponseType.Code,
    scopes: ['openid', 'profile', 'email'],
    usePKCE: true,
  }, discovery);

  useEffect(() => {
    void Promise.all([
      SecureStore.getItemAsync('opsbridge.access-token'),
      SecureStore.getItemAsync('opsbridge.refresh-token'),
    ]).then(([access, refresh]) => { setAccessToken(access); setRefreshToken(refresh); });
  }, []);

  useEffect(() => {
    if (response?.type !== 'success' || !request?.codeVerifier || !discovery) return;
    const code = response.params.code;
    if (!code || exchangedCode.current === code) return;
    exchangedCode.current = code;
    void AuthSession.exchangeCodeAsync({
      clientId,
      code,
      redirectUri,
      extraParams: { code_verifier: request.codeVerifier },
    }, discovery).then(async (tokens) => {
      await SecureStore.setItemAsync('opsbridge.access-token', tokens.accessToken);
      if (tokens.refreshToken) await SecureStore.setItemAsync('opsbridge.refresh-token', tokens.refreshToken);
      if (tokens.expiresIn) await SecureStore.setItemAsync('opsbridge.expires-at', String(Date.now() + tokens.expiresIn * 1000));
      setAccessToken(tokens.accessToken);
      setRefreshToken(tokens.refreshToken ?? null);
    }).catch(() => setAccessToken(null));
  }, [response, request, discovery]);

  async function headers() {
    let storedToken = accessToken ?? await SecureStore.getItemAsync('opsbridge.access-token');
    const storedRefreshToken = refreshToken ?? await SecureStore.getItemAsync('opsbridge.refresh-token');
    const expiry = Number(await SecureStore.getItemAsync('opsbridge.expires-at') ?? '0');
    if (storedToken && expiry && expiry < Date.now() + 30_000 && storedRefreshToken && discovery) {
      const refreshed = await AuthSession.refreshAsync({ clientId, refreshToken: storedRefreshToken }, discovery);
      storedToken = refreshed.accessToken;
      await SecureStore.setItemAsync('opsbridge.access-token', refreshed.accessToken);
      if (refreshed.refreshToken) {
        await SecureStore.setItemAsync('opsbridge.refresh-token', refreshed.refreshToken);
        setRefreshToken(refreshed.refreshToken);
      }
      if (refreshed.expiresIn) await SecureStore.setItemAsync('opsbridge.expires-at', String(Date.now() + refreshed.expiresIn * 1000));
      setAccessToken(refreshed.accessToken);
    }
    return storedToken
      ? { Authorization: `Bearer ${storedToken}` }
      : { 'X-Tenant-Id': 'demo-tenant' };
  }

  async function logout() {
    await SecureStore.deleteItemAsync('opsbridge.access-token');
    await SecureStore.deleteItemAsync('opsbridge.refresh-token');
    await SecureStore.deleteItemAsync('opsbridge.expires-at');
    setAccessToken(null);
    setRefreshToken(null);
  }

  return { accessToken, identityConfigured: Boolean(issuer), ready: Boolean(discovery), signIn: () => promptAsync(), headers, logout, request };
}
