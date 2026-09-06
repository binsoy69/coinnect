import { API_BASE } from "../constants/api";

let bootstrap;
export async function walletRequest(path, options = {}) {
  let token = sessionStorage.getItem("ewalletSession");
  if (!token) {
    bootstrap ??= fetch(`${API_BASE}/ewallet/session`, { method: "POST" })
      .then(async response => {
        if (!response.ok) throw new Error("Cannot open a kiosk session");
        const data = await response.json();
        sessionStorage.setItem("ewalletSession", data.token);
        return data.token;
      }).finally(() => { bootstrap = null; });
    token = await bootstrap;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Kiosk-Session": token, ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail?.message || data.detail || `Request failed (${response.status})`);
    error.code = data.detail?.code;
    throw error;
  }
  return data;
}
