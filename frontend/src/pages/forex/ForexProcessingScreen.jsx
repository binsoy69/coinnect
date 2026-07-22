import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import LoadingDots from '../../components/common/LoadingDots';
import { ROUTES, getForexRoute } from '../../constants/routes';
import { useForex } from '../../context/ForexContext';
import { useForexTransaction } from '../../hooks/useForexTransaction';
import { FOREX_TIMER_DURATIONS } from '../../constants/forexData';

export default function ForexProcessingScreen() {
  const navigate = useNavigate();
  const { forex } = useForex();
  const { backendState, dispenseProgress, transactionId, confirmForexTransaction } = useForexTransaction();
  const statusText =
    dispenseProgress?.dispensed != null && dispenseProgress?.total != null
      ? `Dispensing ${dispenseProgress.dispensed}/${dispenseProgress.total}`
      : "Dispensing Money";

  // Trigger forex transaction confirmation on mount
  useEffect(() => {
    if (transactionId) {
      confirmForexTransaction().catch((err) => {
        console.error("Error confirming forex transaction on processing mount:", err);
        navigate(getForexRoute(ROUTES.FOREX_WARNING, forex.serviceType));
      });
    }
  }, [confirmForexTransaction, transactionId, navigate, forex.serviceType]);

  // Navigate to success or warning when backend signals completion or error
  useEffect(() => {
    if (backendState?.state === "completed" || backendState?.state === "COMPLETED") {
      const timer = setTimeout(() => {
        navigate(getForexRoute(ROUTES.FOREX_SUCCESS, forex.serviceType));
      }, 500);
      return () => clearTimeout(timer);
    } else if (backendState?.state === "ERROR" || backendState?.claim_ticket_code) {
      const timer = setTimeout(() => {
        navigate(getForexRoute(ROUTES.FOREX_WARNING, forex.serviceType));
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [backendState, navigate, forex.serviceType]);

  // Fallback: auto-advance if no backend transaction
  useEffect(() => {
    if (transactionId) return; // Backend will signal completion
    const timer = setTimeout(() => {
      navigate(getForexRoute(ROUTES.FOREX_SUCCESS, forex.serviceType));
    }, FOREX_TIMER_DURATIONS.AUTO_ADVANCE);

    return () => clearTimeout(timer);
  }, [navigate, forex.serviceType, transactionId]);

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
