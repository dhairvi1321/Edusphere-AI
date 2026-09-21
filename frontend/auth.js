const API = 'http://127.0.0.1:8000/api';
const SESSION_KEY = 'edusphere_session';

const Auth = {
  getSession() {
    const s = localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY);
    return s ? JSON.parse(s) : null;
  },

  saveSession(data, remember) {
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
        const msg = data.username?.[0] || data.email?.[0] || data.password?.[0] || 'Registration failed.';
        return { ok: false, error: msg };
      }
      return { ok: true };
    } catch {
      return { ok: false, error: 'Cannot connect to server.' };
    }
  },

  async login(email, password, remember) {
    try {
      const res = await fetch(`${API}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: email, password })
      });
      const data = await res.json();
      if (!res.ok) return { ok: false, error: 'Invalid email or password.' };
      const session = {
        access: data.access,
        refresh: data.refresh,
        email,
        name: email.split('@')[0]
      };
      this.saveSession(session, remember);
      return { ok: true, user: session };
    } catch {
      return { ok: false, error: 'Cannot connect to server.' };
    }
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
