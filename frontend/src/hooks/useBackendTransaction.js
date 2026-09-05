import { useState, useEffect, useCallback, useRef } from "react";
import { API_BASE } from "../constants/api";
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
  const {
    backendTransactionId,
    setBackendTransactionId,
    backendState,
    setBackendState,
    dispenseProgress,
    setDispenseProgress,
    applyAuthoritativeTerms,
  } = useTransaction();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const txIdRef = useRef(null);

  // Keep ref in sync with shared context value
  useEffect(() => {
    txIdRef.current = backendTransactionId;
  }, [backendTransactionId]);

  const createQuote = useCallback(async (type, amount, requestedCounts = null) => {
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/transaction/quote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type,
          amount,
          requested_counts: requestedCounts,
        }),
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        const err = new Error(errData.detail?.message || errData.detail || `HTTP ${resp.status}`);
        err.code = errData.detail?.code;
        throw err;
      }
      return await resp.json();
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchOptions = useCallback(async (type) => {
    try {
      const resp = await fetch(`${API_BASE}/transaction/options?type=${encodeURIComponent(type)}`);
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail?.message || errData.detail || `HTTP ${resp.status}`);
      }
      return await resp.json();
    } catch (err) {
      console.warn("fetchOptions error:", err);
      return null;
    }
  }, []);

  const startBackendTransaction = useCallback(
    async (type, amount, dispenseDenoms = [], dispenseCounts = null, quoteId = null) => {
      setIsLoading(true);
      setError(null);
      try {
        const body = {
          type,
          amount,
          selected_dispense_denoms: dispenseDenoms,
          selected_dispense_counts: dispenseCounts,
        };
        if (quoteId) {
          body.quote_id = quoteId;
        }
        const resp = await fetch(`${API_BASE}/transaction/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          const err = new Error(errData.detail?.message || errData.detail || `HTTP ${resp.status}`);
          err.status = resp.status;
          err.code = errData.detail?.code;
          err.quote = errData.detail?.quote;
          if (errData.detail?.transaction_id) setBackendTransactionId(errData.detail.transaction_id);
          throw err;
        }
        const data = await resp.json();
        setBackendTransactionId(data.transaction_id);
        setBackendState(data);
        applyAuthoritativeTerms(data);
        return data;
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [applyAuthoritativeTerms, setBackendState, setBackendTransactionId]
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
        const err = new Error(errData.detail?.message || errData.detail || `HTTP ${resp.status}`);
        err.status = resp.status;
        err.code = errData.detail?.code;
        err.pendingQuote = errData.detail?.pending_quote;
        throw err;
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

  const approveQuote = useCallback(async (quoteId) => {
    if (!backendTransactionId) return null;
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${API_BASE}/transaction/${backendTransactionId}/approve-quote`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ quote_id: quoteId }),
        }
      );
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail?.message || errData.detail || `HTTP ${resp.status}`);
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

  const requestClaim = useCallback(async () => {
    if (!backendTransactionId) return null;
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${API_BASE}/transaction/${backendTransactionId}/claim`,
        { method: "POST" }
      );
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail?.message || errData.detail || `HTTP ${resp.status}`);
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

  const recordActivity = useCallback(async () => {
    if (!backendTransactionId) return null;
    try {
      const resp = await fetch(
        `${API_BASE}/transaction/${backendTransactionId}/activity`,
        { method: "POST" }
      );
      if (resp.ok) {
        const data = await resp.json();
        setBackendState(data);
        return data;
      }
    } catch (err) {
      console.warn("recordActivity warning:", err);
    }
    return null;
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
        throw new Error(errData.detail?.message || errData.detail || `HTTP ${resp.status}`);
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
        throw new Error(errData.detail?.message || errData.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setBackendState(data);
      setBackendTransactionId(null);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setIsLoading(false);
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
      const snapshot = await resp.json();
      setBackendState(snapshot);
      return snapshot;
    } catch (err) {
      console.error("Simulate insert error:", err);
      return null;
    }
  }, [backendTransactionId, setBackendState]);

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
    createQuote,
    fetchOptions,
    approveQuote,
    requestClaim,
    recordActivity,
  };
}
