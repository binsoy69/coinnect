import { useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import LoadingDots from '../../components/common/LoadingDots';
import { ROUTES, getForexRoute } from '../../constants/routes';
import { useForex } from '../../context/ForexContext';
import { useForexTransaction } from '../../hooks/useForexTransaction';

export default function ForexProcessingScreen() {
  const navigate = useNavigate();
  const { forex } = useForex();
  const {
    backendState,
    transactionId,
    confirmForexTransaction,
    refreshForexTransaction,
  } = useForexTransaction();
  const navigationComplete = useRef(false);
  const submitted = useRef(false);
  const statusText = Object.entries(backendState?.payout_legs || {})
    .map(([name, leg]) => `${name === "CHANGE" ? "Change" : "Exchange"}: ${leg.currency} ${leg.confirmed || 0}/${leg.plan.total_amount}`)
    .join(" · ") || "Dispensing money";

  const handleState = useCallback((data) => {
    if (navigationComplete.current) return true;
    if (data?.state === "COMPLETE") {
      navigationComplete.current = true;
      navigate(getForexRoute(ROUTES.FOREX_SUCCESS, forex.serviceType));
      return true;
    }
    if (
      data?.state === "ERROR" || data?.state === "CLAIM_REQUIRED" || data?.state === "CANCELLED" ||
      Boolean(data?.claim_ticket_code) ||
      data?.shortfall != null
    ) {
      navigationComplete.current = true;
      navigate(getForexRoute(ROUTES.FOREX_WARNING, forex.serviceType));
      return true;
    }
    return false;
  }, [navigate, forex.serviceType]);

  // Trigger forex transaction confirmation on mount
  useEffect(() => {
    if (!transactionId) {
      navigate(getForexRoute(ROUTES.FOREX_WARNING, forex.serviceType));
      return;
    }
    if (submitted.current) return;
    submitted.current = true;
    confirmForexTransaction()
      .then(handleState)
      .catch(async (err) => {
        console.error("Error confirming forex transaction on processing mount:", err);
        const recovered = await refreshForexTransaction().catch(() => null);
        if (!handleState(recovered)) {
          navigate(getForexRoute(ROUTES.FOREX_WARNING, forex.serviceType));
        }
      });
  }, [
    confirmForexTransaction,
    forex.serviceType,
    handleState,
    navigate,
    refreshForexTransaction,
    transactionId,
  ]);

  // Navigate to success or warning when backend signals completion or error
  useEffect(() => {
    handleState(backendState);
  }, [backendState, handleState]);

  return (
    <div className="min-h-screen bg-coinnect-forex flex flex-col items-center justify-center">
      {/* Loading Animation */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="mb-8"
      >
        <LoadingDots count={5} color="white" />
      </motion.div>

      {/* Text */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="text-center text-white"
      >
        <h1 className="text-3xl font-bold mb-2">{statusText}</h1>
        <p className="text-xl">Please wait...</p>
      </motion.div>
    </div>
  );
}
