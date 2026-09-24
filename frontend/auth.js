const API = 'http://127.0.0.1:8000/api';
const SESSION_KEY = 'edusphere_session';

const Auth = {
  getSession() {
    const s = localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY);
    return s ? JSON.parse(s) : null;
  },

  saveSession(data, remember = true) {
    const store = remember ? localStorage : sessionStorage;
    store.setItem(SESSION_KEY, JSON.stringify(data));
  },

  getToken() {
    return this.getSession()?.access || null;
  },

  async register(name, email, password) {
    try {
      const res = await fetch(`${API}/auth/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: email, email, password, first_name: name })
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = data.username?.[0] || data.email?.[0] || data.password?.[0] || data.detail || 'Registration failed.';
        return { ok: false, error: msg };
      }
      return { ok: true };
    } catch {
      return { ok: false, error: 'Cannot connect to server. Make sure the backend is running.' };
    }
  },

  async login(email, password, remember = true) {
    try {
      const res = await fetch(`${API}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: email, password })
      });
      const data = await res.json();
      if (!res.ok) {
        return { ok: false, error: data.detail || 'Invalid email or password.' };
      }
      return await this._finalizeLogin(data, email, remember);
    } catch {
      return { ok: false, error: 'Cannot connect to server. Make sure the backend is running.' };
    }
  },

  async googleLogin(credential, remember = true) {
    try {
      const res = await fetch(`${API}/auth/google/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential })
      });
      const data = await res.json();
      if (!res.ok) {
        return { ok: false, error: data.detail || 'Google login failed.' };
      }
      return await this._finalizeLogin(data, null, remember);
    } catch {
      return { ok: false, error: 'Cannot connect to server. Make sure the backend is running.' };
    }
  },

  async _finalizeLogin(tokenData, emailFallback, remember) {
    let name = emailFallback ? emailFallback.split('@')[0] : 'Student';
    let email = emailFallback || '';
    try {
      const meRes = await fetch(`${API}/auth/me/`, {
        headers: { Authorization: `Bearer ${tokenData.access}` }
      });
      if (meRes.ok) {
        const me = await meRes.json();
        name = me.name || name;
        email = me.email || email;
      }
    } catch { /* use fallback */ }

    const session = { access: tokenData.access, refresh: tokenData.refresh, email, name };
    this.saveSession(session, remember);
    return { ok: true, user: session };
  },

  logout() {
    localStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(SESSION_KEY);
    window.location.href = 'index.html';
  },

  requireAuth() {
    if (!this.getSession()) window.location.href = 'login.html';
  },

  async apiFetch(path, options = {}) {
    const token = this.getToken();
    const res = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {})
      }
    });
    if (res.status === 401) { this.logout(); return null; }
    return res.ok ? res.json() : null;
  }
};
