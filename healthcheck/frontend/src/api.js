const API_BASE =
  import.meta.env.VITE_HEALTHCHECK_API_BASE || 'http://localhost:8010/api/v1';

export const TOKEN_KEY = 'coinnect_healthcheck_token';

async function request(path, { token, ...options } = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
}

export function login(pin) {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ pin }),
  });
}

export function fetchComponents(token) {
  return request('/components', { token });
}

export function fetchStatus(token) {
  return request('/status', { token });
}

export function fetchRecentRuns(token) {
  return request('/runs/recent', { token });
}

export function runTest(token, testId) {
  return request(`/tests/${testId}/run`, {
    method: 'POST',
    token,
  });
}
