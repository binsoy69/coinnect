import { customerFailure } from "./customerErrors";
import { API_BASE } from "../constants/api";

let bootstrap;
export async function walletRequest(path, options = {}) {
  let token = sessionStorage.getItem("ewalletSession");
  if (!token) {
    bootstrap ??= fetch(`${API_BASE}/ewallet/session`, { method: "POST" })
      .then(async response => {
        if (!response.ok) throw new Error("Cannot open a kiosk session");
        const data = await response.json();
        if (typeof data?.token !== "string" || !data.token) throw customerFailure({}, response.status);
        sessionStorage.setItem("ewalletSession", data.token);
        return data.token;
      }).finally(() => { bootstrap = null; });
    token = await bootstrap;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Kiosk-Session": token, ...options.headers },
  });
  let data;
  try { data = await response.json(); }
  catch { throw customerFailure({}, response.status); }
  if (!response.ok) {
    const error = customerFailure(data, response.status);
    throw error;
  }
  return data;
}
