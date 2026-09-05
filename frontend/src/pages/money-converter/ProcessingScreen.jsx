import { useNavigate, useParams } from "react-router-dom";
import { useEffect, useState, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import LoadingDots from "../../components/common/LoadingDots";
import PageTransition from "../../components/layout/PageTransition";
import PayoutReapprovalModal from "../../components/transaction/PayoutReapprovalModal";
import { ROUTES, getServiceRoute } from "../../constants/routes";
import { useWebSocket } from "../../context/WebSocketContext";
import { useBackendTransaction } from "../../hooks/useBackendTransaction";

const SAFETY_TIMEOUT = 30000; // 30s fallback

export default function ProcessingScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { isConnected } = useWebSocket();
  const {
    confirmBackendTransaction,
    refreshBackendTransaction,
    approveQuote,
    requestClaim,
    transactionId,
    backendState,
  } = useBackendTransaction();
  const [progressText, setProgressText] = useState("Please wait...");
  const [isDone, setIsDone] = useState(false);
  const [pendingQuote, setPendingQuote] = useState(null);
  const [isApproving, setIsApproving] = useState(false);
  const isDoneRef = useRef(false);
  const submittedRef = useRef(null);

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
        data?.state === "CLAIM_REQUIRED" || data?.state === "CANCELLED"
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

    if (submittedRef.current === transactionId) return;
    submittedRef.current = transactionId;
    confirmBackendTransaction()
      .then((data) => {
        handleState(data);
      })
      .catch(async (err) => {
        if (err.code === "PAYOUT_REAPPROVAL_REQUIRED" || err.pendingQuote) {
          setPendingQuote(err.pendingQuote || backendState?.pending_quote);
          return;
        }
        console.error("Error confirming transaction on processing mount:", err);
        const recovered = await refreshBackendTransaction().catch(() => null);
        if (Boolean(recovered?.pending_quote) && recovered?.pending_quote) {
          setPendingQuote(recovered.pending_quote);
          return;
        }
        if (!handleState(recovered)) {
          if (recovered?.can_confirm) navigate(getServiceRoute(ROUTES.TRANSACTION_SUMMARY, type));
          else setProgressText("Verifying the transaction status. Please wait...");
        }
      });
  }, [
    confirmBackendTransaction,
    backendState?.pending_quote,
    handleComplete,
    handleState,
    refreshBackendTransaction,
    transactionId,
    navigate,
    type,
  ]);

  useEffect(() => {
    if (backendState?.pending_quote) setPendingQuote(backendState.pending_quote);
    handleState(backendState);
  }, [backendState, handleState]);

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

      <PayoutReapprovalModal
        pendingQuote={pendingQuote || backendState?.pending_quote}
        onApprove={async (quoteId) => {
          setIsApproving(true);
          try {
            await approveQuote(quoteId);
            setPendingQuote(null);
            const data = await confirmBackendTransaction();
            handleState(data);
          } catch (e) {
            console.error("Failed to approve revised quote:", e);
          } finally {
            setIsApproving(false);
          }
        }}
        onRequestClaim={async () => {
          try {
            await requestClaim();
            handleComplete(false);
          } catch (e) {
            console.error("Failed to request claim:", e);
            handleComplete(false);
          }
        }}
        isLoading={isApproving}
      />
    </PageTransition>
  );
}
