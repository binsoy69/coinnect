import { useNavigate, useParams } from "react-router-dom";
import { useEffect, useState, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import LoadingDots from "../../components/common/LoadingDots";
import PageTransition from "../../components/layout/PageTransition";
import { ROUTES, getServiceRoute } from "../../constants/routes";
import { useWebSocket } from "../../context/WebSocketContext";
import { useBackendTransaction } from "../../hooks/useBackendTransaction";

const SAFETY_TIMEOUT = 30000; // 30s fallback

export default function ProcessingScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { subscribe, unsubscribe, isConnected } = useWebSocket();
  const {
    confirmBackendTransaction,
    refreshBackendTransaction,
    transactionId,
  } = useBackendTransaction();
  const [progressText, setProgressText] = useState("Please wait...");
  const [isDone, setIsDone] = useState(false);
  const isDoneRef = useRef(false);

  const handleComplete = useCallback(
    (success) => {
      if (isDoneRef.current) return;
      isDoneRef.current = true;
      setIsDone(true);
      if (success) {
        navigate(getServiceRoute(ROUTES.SUCCESS, type));
      } else {
        navigate(getServiceRoute(ROUTES.WARNING, type));
      }
    },
    [navigate, type]
  );

  const handleState = useCallback(
    (data) => {
      if (data?.state === "COMPLETE") {
        handleComplete(true);
        return true;
      }
      if (
        data?.state === "ERROR" ||
        Boolean(data?.claim_ticket_code) ||
        data?.shortfall != null
      ) {
        handleComplete(false);
        return true;
      }
      return false;
    },
    [handleComplete]
  );

  // Trigger transaction confirmation on mount
  useEffect(() => {
    if (!transactionId) {
      isDoneRef.current = true;
      navigate(getServiceRoute(ROUTES.WARNING, type));
      return;
    }

    confirmBackendTransaction()
      .then((data) => {
        handleState(data);
      })
      .catch(async (err) => {
        console.error("Error confirming transaction on processing mount:", err);
        const recovered = await refreshBackendTransaction().catch(() => null);
        if (!handleState(recovered)) {
          handleComplete(false);
        }
      });
  }, [
    confirmBackendTransaction,
    handleComplete,
    handleState,
    refreshBackendTransaction,
    transactionId,
    navigate,
    type,
  ]);

  // Subscribe to dispense events
  useEffect(() => {
    const handleProgress = (event) => {
      const { completed_items, total_items } = event.payload || {};
      if (total_items) {
        setProgressText(
          `Dispensing ${completed_items}/${total_items} items...`
        );
      }
    };

    const handleDispenseComplete = (event) => {
      const success = event.payload?.success !== false;
      handleComplete(success);
    };

    const handleTransactionComplete = () => {
      handleComplete(true);
    };

    const handleTransactionError = () => {
      handleComplete(false);
    };

    subscribe("DISPENSE_PROGRESS", handleProgress);
    subscribe("DISPENSE_COMPLETE", handleDispenseComplete);
    subscribe("TRANSACTION_COMPLETE", handleTransactionComplete);
    subscribe("TRANSACTION_ERROR", handleTransactionError);

    return () => {
      unsubscribe("DISPENSE_PROGRESS", handleProgress);
      unsubscribe("DISPENSE_COMPLETE", handleDispenseComplete);
      unsubscribe("TRANSACTION_COMPLETE", handleTransactionComplete);
      unsubscribe("TRANSACTION_ERROR", handleTransactionError);
    };
  }, [subscribe, unsubscribe, handleComplete]);

  // Safety timeout: if no WS events received, navigate after 30s
  // Also handles case when WS is not connected (offline/demo mode)
  useEffect(() => {
    if (isDone) return undefined;

    const timer = setTimeout(async () => {
      const recovered = await refreshBackendTransaction().catch(() => null);
      if (!handleState(recovered) && !isDoneRef.current) {
        setProgressText(
          isConnected
            ? "Still processing. Verifying transaction status..."
            : "Connection interrupted. Verifying transaction status..."
        );
      }
    }, isConnected ? SAFETY_TIMEOUT : 2500);

    return () => clearTimeout(timer);
  }, [isDone, isConnected, handleState, refreshBackendTransaction]);

  return (
    <PageTransition>
      <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center text-white"
        >
          {/* Loading dots */}
          <LoadingDots count={5} color="white" className="mb-8" />

          {/* Status text */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-3xl font-bold mb-3"
          >
            Dispensing Money
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-lg text-white/80"
          >
            {progressText}
          </motion.p>
        </motion.div>
      </div>
    </PageTransition>
  );
}
