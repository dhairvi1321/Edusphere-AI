const API = 'http://127.0.0.1:8000/api';
const SESSION_KEY = 'edusphere_session';

async function fetchWithTimeout(url, options = {}, timeoutMs = 20000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

function connectionError(error) {
  return error?.name === 'AbortError'
    ? 'The server took too long to respond. Please check the database connection and try again.'
    : 'Cannot connect to server. Make sure the backend is running.';
}

const Auth = {
  getSession() {
    const s = localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY);
    return s ? JSON.parse(s) : null;
  },

  saveSession(data, remember = true) {
    localStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(SESSION_KEY);
    const store = remember ? localStorage : sessionStorage;
    store.setItem(SESSION_KEY, JSON.stringify(data));
  },

  getToken() {
    return this.getSession()?.access || null;
  },

  async register(name, email, password) {
    try {
      const res = await fetchWithTimeout(`${API}/auth/register/`, {
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
    } catch (error) {
      return { ok: false, error: connectionError(error) };
    }
  },

  async login(email, password, remember = true) {
    try {
      const res = await fetchWithTimeout(`${API}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: email, password })
      });
      const data = await res.json();
      if (!res.ok) {
        return { ok: false, error: data.detail || 'Invalid email or password.' };
      }
      return await this._finalizeLogin(data, email, remember);
    } catch (error) {
      return { ok: false, error: connectionError(error) };
    }
  },

  async googleLogin(credential, remember = true) {
    try {
      const res = await fetchWithTimeout(`${API}/auth/google/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential })
      });
      const data = await res.json();
      if (!res.ok) {
        return { ok: false, error: data.detail || 'Google login failed.' };
      }
      return await this._finalizeLogin(data, null, remember);
    } catch (error) {
      return { ok: false, error: connectionError(error) };
    }
  },

  async _finalizeLogin(tokenData, emailFallback, remember) {
    let name = emailFallback ? emailFallback.split('@')[0] : 'Student';
    let email = emailFallback || '';
    try {
      const meRes = await fetchWithTimeout(`${API}/auth/me/`, {
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
    const { throwOnError = false, ...fetchOptions } = options;
    const isFormData = typeof FormData !== 'undefined' && fetchOptions.body instanceof FormData;
    const requestHeaders = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(fetchOptions.headers || {})
    };
    try {
      const res = await fetchWithTimeout(`${API}${path}`, {
        ...fetchOptions,
        headers: requestHeaders
      });
      if (res.status === 401) {
        if (!this._loggingOut) {
          this._loggingOut = true;
          this.logout();
        }
        return null;
      }
      if (res.status === 204) return {};
      if (!res.ok) {
        let errBody = null;
        try { errBody = await res.json(); } catch { /* no body */ }
        console.error(`API ${fetchOptions.method || 'GET'} ${path} → ${res.status}`, errBody);
        if (res.status === 503) {
          window.dispatchEvent(new CustomEvent('edusphere:api-error', {
            detail: errBody?.detail || 'Student data is temporarily unavailable. Please try again.'
          }));
        }
        if (throwOnError) throw new Error(errBody?.detail || `Request failed (${res.status}).`);
        return null;
      }
      return res.json();
    } catch (err) {
      console.error(`apiFetch network error on ${path}:`, err);
      if (throwOnError) {
        if (err?.name === 'AbortError') throw new Error(connectionError(err));
        if (err instanceof TypeError) throw new Error('Cannot connect to the server. Please try again.');
        throw err;
      }
      return null;
    }
  }
};
