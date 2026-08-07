import { useState, useEffect, useCallback, useRef } from "react";
import { API_BASE } from "../constants/api";
import { useWebSocket } from "../context/WebSocketContext";
import { useTransaction } from "../context/TransactionContext";

/**
 * Hook bridging the frontend TransactionContext with the backend API.
 *
 * Subscribes to WebSocket events to receive real-time updates about
 * bill insertions, dispense progress, and state changes.
 *
 * The backend transaction ID is stored in TransactionContext so it
 * persists across screen navigations.
 */
export function useBackendTransaction() {
  const { subscribe, unsubscribe } = useWebSocket();
  const {
    addInsertedMoney,
    backendTransactionId,
    setBackendTransactionId,
    backendState,
    setBackendState,
    dispenseProgress,
    setDispenseProgress,
  } = useTransaction();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const txIdRef = useRef(null);

  // Keep ref in sync with shared context value
  useEffect(() => {
    txIdRef.current = backendTransactionId;
  }, [backendTransactionId]);

  // Subscribe to transaction events
  useEffect(() => {
    const handleStateChange = (event) => {
      if (event.payload?.transaction_id === txIdRef.current) {
        setBackendState(event.payload);
      }
    };

    const handleBillStored = (event) => {
      if (event.payload) {
        const value = event.payload.value;
        if (value) {
          addInsertedMoney(value);
        }
      }
    };

    const handleCoinInserted = (event) => {
      if (event.payload) {
        const denom = event.payload.denomination;
        if (denom) {
          addInsertedMoney(denom);
        }
      }
    };

    const handleDispenseProgress = (event) => {
      setDispenseProgress(event.payload);
    };

    const handleError = (event) => {
      if (event.payload?.transaction_id === txIdRef.current) {
        setBackendState(event.payload);
        setError(event.payload?.error_message || "Transaction error");
      }
    };

    subscribe("TRANSACTION_STATE_CHANGED", handleStateChange);
    subscribe("TRANSACTION_COMPLETE", handleStateChange);
    subscribe("TRANSACTION_CANCELLED", handleStateChange);
    subscribe("TRANSACTION_ERROR", handleError);
    subscribe("BILL_STORED", handleBillStored);
    subscribe("COIN_INSERTED", handleCoinInserted);
    subscribe("DISPENSE_PROGRESS", handleDispenseProgress);

    return () => {
      unsubscribe("TRANSACTION_STATE_CHANGED", handleStateChange);
      unsubscribe("TRANSACTION_COMPLETE", handleStateChange);
      unsubscribe("TRANSACTION_CANCELLED", handleStateChange);
      unsubscribe("TRANSACTION_ERROR", handleError);
      unsubscribe("BILL_STORED", handleBillStored);
      unsubscribe("COIN_INSERTED", handleCoinInserted);
      unsubscribe("DISPENSE_PROGRESS", handleDispenseProgress);
    };
  }, [
    subscribe,
    unsubscribe,
    addInsertedMoney,
    setBackendState,
    setDispenseProgress,
  ]);

  const startBackendTransaction = useCallback(
    async (type, amount, fee, dispenseDenoms = [], dispenseCounts = null) => {
      setIsLoading(true);
      setError(null);
      try {
        const resp = await fetch(`${API_BASE}/transaction/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            type,
            amount,
            fee,
            selected_dispense_denoms: dispenseDenoms,
            selected_dispense_counts: dispenseCounts,
          }),
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || `HTTP ${resp.status}`);
        }
        const data = await resp.json();
        setBackendTransactionId(data.transaction_id);
        setBackendState(data);
        return data;
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [setBackendState, setBackendTransactionId]
  );

  const confirmBackendTransaction = useCallback(async () => {
    if (!backendTransactionId) return null;
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${API_BASE}/transaction/${backendTransactionId}/confirm`,
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
  }, [backendTransactionId, setBackendState]);

  const refreshBackendTransaction = useCallback(async () => {
    if (!backendTransactionId) return null;
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${API_BASE}/transaction/${backendTransactionId}`
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
  }, [backendTransactionId, setBackendState]);

  const cancelBackendTransaction = useCallback(async () => {
    if (!backendTransactionId) return null;
    setIsLoading(true);
    try {
      const resp = await fetch(
        `${API_BASE}/transaction/${backendTransactionId}`,
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
      setBackendTransactionId(null);
    }
  }, [
    backendTransactionId,
    setBackendState,
    setBackendTransactionId,
  ]);

  const simulateInsert = useCallback(async (denom, insertType = "bill") => {
    if (!backendTransactionId) return null;
    try {
      const resp = await fetch(
        `${API_BASE}/transaction/${backendTransactionId}/simulate-insert`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ denom, insert_type: insertType }),
        }
      );
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      return await resp.json();
    } catch (err) {
      console.error("Simulate insert error:", err);
      return null;
    }
  }, [backendTransactionId]);

  const resetBackendTransaction = useCallback(() => {
    setBackendTransactionId(null);
    setBackendState(null);
    setError(null);
    setDispenseProgress(null);
  }, [
    setBackendState,
    setBackendTransactionId,
    setDispenseProgress,
  ]);

  return {
    transactionId: backendTransactionId,
    backendState,
    isLoading,
    error,
    dispenseProgress,
    startBackendTransaction,
    confirmBackendTransaction,
    refreshBackendTransaction,
    cancelBackendTransaction,
    simulateInsert,
    resetBackendTransaction,
  };
}
