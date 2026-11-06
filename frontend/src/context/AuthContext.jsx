import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, getToken, setToken, setUnauthorizedHandler } from '../services/api';

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!getToken());

  const clear = useCallback(() => { setToken(null); setUser(null); }, []);

  useEffect(() => {
    setUnauthorizedHandler(clear);
    if (!getToken()) return;
    api.get('/auth/me').then(setUser).catch(clear).finally(() => setLoading(false));
  }, [clear]);

  const finish = (res) => { setToken(res.access_token); setUser(res.user); return res.user; };
  const login = async (email, password) => finish(await api.post('/auth/login', { email, password }));
  const register = async (payload) => finish(await api.post('/auth/register', payload));
  const logout = async () => {
    try { await api.post('/auth/logout'); } catch { /* ignore */ }
    clear();
  };

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>;
}
