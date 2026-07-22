import { useState, useEffect, useRef } from "react";
import { API_BASE } from "../constants/api";
import { useWebSocket } from "../context/WebSocketContext";

/**
 * Hook to manage physical bill acceptance loop for a given transaction.
 *
 * @param {string} transactionId - Active transaction ID
 * @param {string} apiPrefix - Endpoint prefix (e.g. '/transaction', '/ewallet/transactions', '/forex/transaction')
 * @param {boolean} enabled - Whether polling is active
 * @param {function} onAccepted - Optional callback when bill is accepted (returns state data)
 */
export function useBillAcceptance(transactionId, apiPrefix, enabled, onAccepted) {
  const [isAccepting, setIsAccepting] = useState(false);
  const [isSorting, setIsSorting] = useState(false);
  const [lastError, setLastError] = useState(null);
  const { subscribe, unsubscribe } = useWebSocket();
  const onAcceptedRef = useRef(onAccepted);

  // Keep callback ref updated without re-triggering the polling effect
  useEffect(() => {
    onAcceptedRef.current = onAccepted;
  }, [onAccepted]);

  // Listen for WebSocket events (BILL_ACCEPTING, BILL_SORTING, BILL_STORED, BILL_REJECTED)
  useEffect(() => {
    const handleBillAccepting = () => setIsSorting(true);
    const handleBillSorting = () => setIsSorting(true);
    const handleBillStored = () => setIsSorting(false);
    const handleBillRejected = (event) => {
      setIsSorting(false);
      if (event.payload) {
        setLastError(event.payload.reason || event.payload.error || "BILL_REJECTED");
      }
    };

    subscribe("BILL_ACCEPTING", handleBillAccepting);
    subscribe("BILL_SORTING", handleBillSorting);
    subscribe("BILL_STORED", handleBillStored);
    subscribe("BILL_REJECTED", handleBillRejected);

    return () => {
      unsubscribe("BILL_ACCEPTING", handleBillAccepting);
      unsubscribe("BILL_SORTING", handleBillSorting);
      unsubscribe("BILL_STORED", handleBillStored);
      unsubscribe("BILL_REJECTED", handleBillRejected);
    };
  }, [subscribe, unsubscribe]);

  useEffect(() => {
    if (!transactionId || !enabled || lastError) return undefined;
    let cancelled = false;

    const acceptLoop = async () => {
      setIsAccepting(true);
      while (!cancelled) {
        try {
          const resp = await fetch(`${API_BASE}${apiPrefix}/${transactionId}/accept-bill`, {
            method: "POST",
          });
          
          if (!resp.ok) {
            await new Promise((resolve) => setTimeout(resolve, 1000));
            continue;
          }
          
          const data = await resp.json();
          if (cancelled) break;

          // If backend state is AUTHENTICATING or SORTING, set isSorting
          if (data?.state === "AUTHENTICATING" || data?.state === "SORTING") {
            setIsSorting(true);
          } else {
            setIsSorting(false);
          }

          if (onAcceptedRef.current) {
            onAcceptedRef.current(data);
          }

          if (data?.state === "WAITING_FOR_CONFIRMATION" || data?.state === "COMPLETE") {
            break;
          }

          if (data?.last_rejection || data?.error) {
            setLastError(data.last_rejection || data.error);
          }
        } catch (err) {
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
      setIsAccepting(false);
      setIsSorting(false);
    };

    acceptLoop();

    return () => {
      cancelled = true;
    };
  }, [transactionId, apiPrefix, enabled, lastError]);

  const clearError = () => {
    setLastError(null);
    setIsSorting(false);
  };

  return { isAccepting, isSorting, lastError, clearError };
}

