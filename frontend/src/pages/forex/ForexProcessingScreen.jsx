import { useEffect, useState } from 'react';
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
  const { backendState, dispenseProgress, transactionId } = useForexTransaction();
  const [statusText, setStatusText] = useState("Dispensing Money");

  // Update status text based on dispense progress
  useEffect(() => {
    if (dispenseProgress) {
      const { dispensed, total } = dispenseProgress;
      if (dispensed != null && total != null) {
        setStatusText(`Dispensing ${dispensed}/${total}`);
      }
    }
  }, [dispenseProgress]);

  // Navigate to success when backend signals completion
  useEffect(() => {
    if (backendState?.state === "completed" || backendState?.state === "COMPLETED") {
      const timer = setTimeout(() => {
        navigate(getForexRoute(ROUTES.FOREX_SUCCESS, forex.serviceType));
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
