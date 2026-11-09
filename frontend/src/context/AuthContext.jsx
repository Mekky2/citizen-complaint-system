import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as authApi from '../api/auth';
import { subscribeLogout } from '../api/client';
import { tokenStore } from '../utils/tokenStore';

const AuthCtx = createContext(null);

export const homePathFor = (role) => `/${role}`; // citizen | supervisor | technician | admin

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // { id, name, role }
  const [booting, setBooting] = useState(() => !!tokenStore.getAccess());

  const logout = useCallback(() => { tokenStore.clear(); setUser(null); }, []);

  // Restore session on reload.
  useEffect(() => {
    if (!tokenStore.getAccess()) return;
    authApi.me().then(setUser).catch(() => tokenStore.clear()).finally(() => setBooting(false));
  }, []);

  // The axios layer tells us when refresh failed.
  useEffect(() => subscribeLogout(() => setUser(null)), []);

  const establish = useCallback(async (tokens) => {
    tokenStore.set(tokens);
    const profile = await authApi.me();
    setUser(profile);
    return profile;
  }, []);

  const login = useCallback(async (identifier, password) => establish(await authApi.login(identifier, password)), [establish]);
  const register = useCallback(async (payload) => establish(await authApi.register(payload)), [establish]);

  const value = useMemo(() => ({ user, booting, login, register, logout }), [user, booting, login, register, logout]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
