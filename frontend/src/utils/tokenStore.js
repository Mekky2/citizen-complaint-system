// Tokens live in sessionStorage so every browser tab keeps its own session
// (admin in one tab, citizen in another). Storage can throw (private mode, blocked site data),
// so each access is guarded and falls back to memory for the life of the page.
const ACCESS = 'egco.access';
const REFRESH = 'egco.refresh';
const mem = {};

const read = (k) => { try { return sessionStorage.getItem(k) ?? mem[k] ?? null; } catch { return mem[k] ?? null; } };
const write = (k, v) => {
  if (v == null) delete mem[k]; else mem[k] = v;
  try { v == null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch { /* memory fallback above */ }
};

// Tokens saved by earlier versions in localStorage would leak one login into every tab — drop them once.
try { localStorage.removeItem(ACCESS); localStorage.removeItem(REFRESH); } catch { /* ignore */ }

export const tokenStore = {
  getAccess: () => read(ACCESS),
  getRefresh: () => read(REFRESH),
  set: ({ access_token, refresh_token }) => { write(ACCESS, access_token); write(REFRESH, refresh_token); },
  clear: () => { write(ACCESS, null); write(REFRESH, null); },
};
