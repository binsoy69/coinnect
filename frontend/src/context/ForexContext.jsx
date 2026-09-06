/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";
import { API_BASE, ENABLE_KEYBOARD_SIM } from "../constants/api";
import { FOREX_CONFIG } from "../constants/forexData";
import { useWebSocket } from "./WebSocketContext";

const ForexContext = createContext(null);
const TERMINAL = ["COMPLETE", "CLAIM_REQUIRED", "CANCELLED", "ERROR", "RESOLVED"];
export function ForexProvider({ children }) {
  const { subscribe, unsubscribe, isConnected } = useWebSocket();
  const [transactionId, setTransactionId] = useState(() => sessionStorage.getItem("forexTransaction"));
  const [backendState, setBackendState] = useState(null);
  const [service, setService] = useState(() => sessionStorage.getItem("forexService"));
  const [quote, setQuote] = useState(null);
  const [rates, setRates] = useState({ rates: {}, online: false, valid: false, availability: {} });
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [clock, setClock] = useState(Date.now());
  const stateRef = useRef(null);
  const quoteSequence = useRef(0);
  const refreshPending = useRef(null);
  const apply = useCallback(data => {
    const old = stateRef.current;
    if (old?.transaction_id === data.transaction_id && (old.revision || 0) > (data.revision || 0)) return old;
    stateRef.current = data;
    setBackendState(data);
    setTransactionId(data.transaction_id);
    sessionStorage.setItem("forexTransaction", data.transaction_id);
    if (data.quote) setQuote(data.quote);
    if (data.type?.startsWith("forex-")) {
      const selected = data.type.slice(6);
      setService(selected);
      sessionStorage.setItem("forexService", selected);
    }
    return data;
  }, []);
  const request = useCallback(async (path, options = {}) => {
    const resp = await fetch(`${API_BASE}/forex${path}`, {
      signal: AbortSignal.timeout(15000), ...options, headers: { "Content-Type": "application/json", ...options.headers },
    });
    const data = await resp.json();
    if (!resp.ok) { const failure = new Error(data.detail?.message || data.detail || `HTTP ${resp.status}`); failure.status = resp.status; throw failure; }
    return data;
  }, []);
  const run = useCallback(async action => {
    setError(null); setIsLoading(true);
    try { return await action(); }
    catch (err) { setError(err.message); throw err; }
    finally { setIsLoading(false); }
  }, []);
  const refreshForexTransaction = useCallback(() => {
    if (!transactionId) return Promise.resolve(null);
    if (refreshPending.current) return refreshPending.current;
    refreshPending.current = run(async () => apply(await request(`/transaction/${transactionId}`)))
      .finally(() => { refreshPending.current = null; });
    return refreshPending.current;
  }, [transactionId, run, apply, request]);
  const checkConnectivity = useCallback(async () => {
    try {
      const data = await request("/rates"); setRates(data);
      return { online: data.online, forex_available: data.online && data.valid && data.enabled !== false };
    } catch { setRates(old => ({ ...old, online: false })); return { online: false, forex_available: false }; }
  }, [request]);
  useEffect(() => {
    const initial = setTimeout(() => { checkConnectivity(); }, 0);
    const timer = setInterval(() => { setClock(Date.now()); }, 1000);
    return () => { clearTimeout(initial); clearInterval(timer); };
  }, [checkConnectivity]);
  useEffect(() => {
    if (!transactionId) return undefined;
    let failures = 0;
    let timer;
    let disposed = false;
    const refresh = async () => {
      try { await refreshForexTransaction(); failures = 0; }
      catch { failures += 1; }
      if (!disposed && failures < 3 && !TERMINAL.includes(stateRef.current?.state)) timer = setTimeout(refresh, 3000);
    };
    timer = setTimeout(refresh, 0);
    return () => { disposed = true; clearTimeout(timer); };
  }, [transactionId, isConnected, refreshForexTransaction]);
  useEffect(() => {
    const update = event => {
      if (event.payload?.transaction_id === transactionId) refreshForexTransaction().catch(() => {});
    };
    const rateUpdate = () => { checkConnectivity(); };
    const events = ["TRANSACTION_STATE_CHANGED", "TRANSACTION_COMPLETE", "TRANSACTION_ERROR", "TRANSACTION_CANCELLED", "CLAIM_TICKET", "DISPENSE_PROGRESS"];
    events.forEach(name => subscribe(name, update));
    ["FOREX_RATE_UPDATE", "FOREX_CONNECTIVITY_CHANGED"].forEach(name => subscribe(name, rateUpdate));
    return () => {
      events.forEach(name => unsubscribe(name, update));
      ["FOREX_RATE_UPDATE", "FOREX_CONNECTIVITY_CHANGED"].forEach(name => unsubscribe(name, rateUpdate));
    };
  }, [subscribe, unsubscribe, transactionId, refreshForexTransaction, checkConnectivity]);
  const resetForexTransaction = useCallback(() => {
    ["forexTransaction", "forexService", "forexStart"].forEach(k => sessionStorage.removeItem(k));
    stateRef.current = null; setTransactionId(null); setBackendState(null); setQuote(null); setService(null); setError(null);
  }, []);
  const startForexTransaction = useCallback(selected => {
    if (transactionId && !TERMINAL.includes(stateRef.current?.state)) throw new Error("Finish the active exchange first");
    resetForexTransaction(); setService(selected); sessionStorage.setItem("forexService", selected);
  }, [transactionId, resetForexTransaction]);
  const setSelectedAmount = useCallback(amount => run(async () => {
    const seq = ++quoteSequence.current;
    setQuote(null);
    const data = await request(`/quote/${service}?amount=${amount}`);
    if (seq === quoteSequence.current) setQuote(data);
    return data;
  }), [service, request, run]);
  const startForexBackendTransaction = useCallback(() => run(async () => {
    let pending;
    try { pending = JSON.parse(sessionStorage.getItem("forexStart")); } catch { /* Ignore invalid saved input. */ }
    if (!pending) {
      if (!quote?.quote_id) throw new Error("Select and review a quote first");
      pending = { quote_id: quote.quote_id, idempotency_key: crypto.randomUUID() };
      sessionStorage.setItem("forexStart", JSON.stringify(pending));
    }
    try {
      const data = apply(await request("/transaction", { method: "POST", body: JSON.stringify(pending) }));
      sessionStorage.removeItem("forexStart");
      return data;
    } catch (err) {
      if (err.status >= 400 && err.status < 500) sessionStorage.removeItem("forexStart");
      throw err;
    }
  }), [quote, request, run, apply]);
  useEffect(() => {
    if (!transactionId && sessionStorage.getItem("forexStart")) startForexBackendTransaction().catch(() => {});
  }, [transactionId, startForexBackendTransaction]);
  const mutate = useCallback((suffix, method = "POST") => run(async () => {
    if (!transactionId) throw new Error("Missing transaction reference");
    return apply(await request(`/transaction/${transactionId}${suffix}`, { method }));
  }), [transactionId, request, run, apply]);
  const confirmForexTransaction = useCallback(() => mutate("/confirm"), [mutate]);
  const cancelForexTransaction = useCallback(() => mutate("", "DELETE"), [mutate]);
  const continueForexTransaction = useCallback(() => mutate("/continue"), [mutate]);
  const simulateForexInsert = useCallback((denom, currency) => run(async () => {
    if (!ENABLE_KEYBOARD_SIM || !transactionId) throw new Error("Simulation is disabled");
    return apply(await request(`/transaction/${transactionId}/simulate-insert`, { method: "POST", body: JSON.stringify({ denom, currency }) }));
  }), [transactionId, run, request, apply]);
  const config = FOREX_CONFIG[service];
  const current = backendState?.quote || quote;
  const counts = Object.fromEntries(Object.entries(backendState?.inserted_denominations || {}).map(([k, v]) => [k.split("_").pop(), v]));
  const forex = { serviceType: service, fromCurrency: current?.from_currency || config?.fromCurrency,
    toCurrency: current?.to_currency || config?.toCurrency, exchangeRate: current?.rate || 0,
    selectedAmount: current?.selected_amount, convertedAmount: current?.converted_amount || 0,
    feeAmount: current?.fee_amount || 0, feePercentage: current?.fee_percentage,
    totalDue: current?.input_amount || 0, amountToDispense: current?.output_amount || 0,
    moneyInserted: backendState?.inserted_amount || 0, insertedCounts: counts, rateLocked: Boolean(transactionId) };
  const secondsRemaining = backendState?.deadline ? Math.max(0, Math.ceil((Date.parse(backendState.deadline) - clock)/1000)) : null;
  const getForexConfig = useCallback(() => FOREX_CONFIG[service] || null, [service]);
  const isAmountMatched = useCallback(() => backendState?.state === "WAITING_FOR_CONFIRMATION", [backendState]);
  const api = { transactionId, backendState, isLoading, error, forexRates: rates.rates || {},
    isOnline: rates.online && rates.valid && rates.enabled !== false, availability: rates.availability || {}, fetchedAt: rates.fetched_at,
    startForexBackendTransaction, confirmForexTransaction, cancelForexTransaction, continueForexTransaction,
    refreshForexTransaction, resetForexTransaction, simulateForexInsert, checkConnectivity, secondsRemaining };
  return <ForexContext.Provider value={{ ...api, api, forex, quote, startForexTransaction,
    setSelectedAmount, getForexConfig, isAmountMatched, backendRates: rates.rates,
    lockRate: () => {}, updateRatesFromBackend: () => {} }}>{children}
    {secondsRemaining != null && secondsRemaining <= 30 && !TERMINAL.includes(backendState?.state) &&
      <aside role="alert" className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-white text-gray-900 shadow-lg rounded-xl p-4 z-50">
        Session expires in {secondsRemaining}s. <button className="underline font-bold" onClick={() => continueForexTransaction().catch(() => {})}>Continue</button>
      </aside>}
    </ForexContext.Provider>;
}
export function useForex() {
  const value = useContext(ForexContext);
  if (!value) throw new Error("useForex must be used within a ForexProvider");
  return value;
}
export default ForexContext;
