/**
 * Hook bridging ForexContext with the backend forex API.
 *
 * Provides:
 * - startForexBackendTransaction(serviceType, amount, dispenseDenoms)
 * - confirmForexTransaction()
 * - cancelForexTransaction()
 * - simulateForexInsert(denom, currency)
 * - forexRates (live rates from backend)
 * - connectivity status
 *
 * Subscribes to WS events:
 * - FOREX_RATE_UPDATE -> update rates
 * - FOREX_RATE_LOCKED -> lock rate in ForexContext
 * - FOREX_CONNECTIVITY_CHANGED -> update online status
 * - BILL_STORED -> update inserted amount in ForexContext
 * - TRANSACTION_STATE_CHANGED -> update state
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { API_BASE } from "../constants/api";
import { useWebSocket } from "../context/WebSocketContext";
import { useForex } from "../context/ForexContext";

export function useForexTransaction() {
  const { subscribe, unsubscribe } = useWebSocket();
  const { addInsertedMoney, lockRate } = useForex();
  const [transactionId, setTransactionId] = useState(null);
  const [backendState, setBackendState] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [forexRates, setForexRates] = useState({});
  const [isOnline, setIsOnline] = useState(false);
  const [dispenseProgress, setDispenseProgress] = useState(null);
  const txIdRef = useRef(null);

  useEffect(() => {
    txIdRef.current = transactionId;
  }, [transactionId]);

  // Fetch initial rates
  useEffect(() => {
    const fetchRates = async () => {
      try {
        const resp = await fetch(`${API_BASE}/forex/rates`);
        if (resp.ok) {
          const data = await resp.json();
          setForexRates(data.rates || {});
          setIsOnline(data.online);
        }
      } catch {
        setIsOnline(false);
      }
    };
    fetchRates();
  }, []);

  // Subscribe to WS events
  useEffect(() => {
    const handleRateUpdate = (event) => {
      setForexRates(event.payload?.rates || {});
    };

    const handleConnectivity = (event) => {
      setIsOnline(event.payload?.online ?? false);
    };

    const handleStateChange = (event) => {
      if (event.payload?.transaction_id === txIdRef.current) {
        setBackendState(event.payload);
      }
    };

    const handleBillStored = (event) => {
      if (event.payload?.value) {
        addInsertedMoney(event.payload.value);
      }
    };

    const handleRateLocked = (event) => {
      if (event.payload?.transaction_id === txIdRef.current) {
        lockRate();
      }
    };

    const handleDispenseProgress = (event) => {
      setDispenseProgress(event.payload);
    };

    const handleError = (event) => {
      if (event.payload?.transaction_id === txIdRef.current) {
        setError(event.payload?.error_message || "Forex transaction error");
      }
    };

    subscribe("FOREX_RATE_UPDATE", handleRateUpdate);
    subscribe("FOREX_CONNECTIVITY_CHANGED", handleConnectivity);
    subscribe("FOREX_RATE_LOCKED", handleRateLocked);
    subscribe("TRANSACTION_STATE_CHANGED", handleStateChange);
    subscribe("TRANSACTION_COMPLETE", handleStateChange);
    subscribe("TRANSACTION_CANCELLED", handleStateChange);
    subscribe("TRANSACTION_ERROR", handleError);
    subscribe("BILL_STORED", handleBillStored);
    subscribe("DISPENSE_PROGRESS", handleDispenseProgress);

    return () => {
      unsubscribe("FOREX_RATE_UPDATE", handleRateUpdate);
      unsubscribe("FOREX_CONNECTIVITY_CHANGED", handleConnectivity);
      unsubscribe("FOREX_RATE_LOCKED", handleRateLocked);
      unsubscribe("TRANSACTION_STATE_CHANGED", handleStateChange);
      unsubscribe("TRANSACTION_COMPLETE", handleStateChange);
      unsubscribe("TRANSACTION_CANCELLED", handleStateChange);
      unsubscribe("TRANSACTION_ERROR", handleError);
      unsubscribe("BILL_STORED", handleBillStored);
      unsubscribe("DISPENSE_PROGRESS", handleDispenseProgress);
    };
  }, [subscribe, unsubscribe, addInsertedMoney, lockRate]);

  const startForexBackendTransaction = useCallback(
    async (serviceType, amount, dispenseDenoms = []) => {
      setIsLoading(true);
      setError(null);
      try {
        const resp = await fetch(`${API_BASE}/forex/transaction`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            service_type: serviceType,
            selected_amount: amount,
            selected_dispense_denoms: dispenseDenoms,
          }),
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || `HTTP ${resp.status}`);
        }
        const data = await resp.json();
        setTransactionId(data.transaction_id);
        setBackendState(data);
        return data;
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const confirmForexTransaction = useCallback(async () => {
    if (!txIdRef.current) return null;
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${API_BASE}/forex/transaction/${txIdRef.current}/confirm`,
        { method: "POST" }
      );
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setBackendState(data);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const cancelForexTransaction = useCallback(async () => {
    if (!txIdRef.current) return null;
    setIsLoading(true);
    try {
      const resp = await fetch(
        `${API_BASE}/forex/transaction/${txIdRef.current}`,
        { method: "DELETE" }
      );
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setBackendState(data);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
      setTransactionId(null);
    }
  }, []);

  const simulateForexInsert = useCallback(
    async (denom, currency = "USD") => {
      if (!txIdRef.current) return null;
      try {
        const resp = await fetch(
          `${API_BASE}/forex/transaction/${txIdRef.current}/simulate-insert`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ denom, currency }),
          }
        );
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || `HTTP ${resp.status}`);
        }
        return await resp.json();
      } catch (err) {
        console.error("Simulate forex insert error:", err);
        return null;
      }
    },
    []
  );

  const resetForexTransaction = useCallback(() => {
    setTransactionId(null);
    setBackendState(null);
    setError(null);
    setDispenseProgress(null);
  }, []);

  const checkConnectivity = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/forex/connectivity`);
      if (resp.ok) {
        const data = await resp.json();
        setIsOnline(data.online);
        return data;
      }
    } catch {
      setIsOnline(false);
    }
    return { online: false, forex_available: false };
  }, []);

  return {
    transactionId,
    backendState,
    isLoading,
    error,
    forexRates,
    isOnline,
    dispenseProgress,
    startForexBackendTransaction,
    confirmForexTransaction,
    cancelForexTransaction,
    simulateForexInsert,
    resetForexTransaction,
    checkConnectivity,
  };
}
