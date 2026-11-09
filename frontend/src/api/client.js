import axios from 'axios';
import { tokenStore } from '../utils/tokenStore';

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api/v1';

const client = axios.create({ baseURL: API_URL, timeout: 30000 });

client.interceptors.request.use((config) => {
  const token = tokenStore.getAccess();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401: try ONE refresh (shared by all concurrent requests), replay the request, else log out.
let refreshing = null;
const onLogout = new Set();
export const subscribeLogout = (fn) => { onLogout.add(fn); return () => onLogout.delete(fn); };

async function doRefresh() {
  const refresh_token = tokenStore.getRefresh();
  if (!refresh_token) throw new Error('no refresh token');
  // bare axios: must not pass through this interceptor again
  const { data } = await axios.post(`${API_URL}/auth/refresh`, { refresh_token });
  tokenStore.set(data);
  return data.access_token;
}

client.interceptors.response.use(
  (r) => r,
  async (error) => {
    const { config, response } = error;
    const isAuthCall = config?.url?.includes('/auth/login') || config?.url?.includes('/auth/refresh') || config?.url?.includes('/auth/register');
    if (response?.status !== 401 || config?._retried || isAuthCall) throw error;

    try {
      refreshing ??= doRefresh().finally(() => { refreshing = null; });
      const token = await refreshing;
      config._retried = true;
      config.headers.Authorization = `Bearer ${token}`;
      return client(config);
    } catch {
      tokenStore.clear();
      onLogout.forEach((fn) => fn());
      throw error;
    }
  },
);

export default client;
