import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import LoadingDots from '../../components/common/LoadingDots';
import { ROUTES, getForexRoute } from '../../constants/routes';
import { useForex } from '../../context/ForexContext';
import { FOREX_TIMER_DURATIONS } from '../../constants/forexData';

export default function ForexProcessingScreen() {
  const navigate = useNavigate();
  const { forex } = useForex();

  // Auto-advance to success screen
  useEffect(() => {
    const timer = setTimeout(() => {
      navigate(getForexRoute(ROUTES.FOREX_SUCCESS, forex.serviceType));
    }, FOREX_TIMER_DURATIONS.AUTO_ADVANCE);

    return () => clearTimeout(timer);
  }, [navigate, forex.serviceType]);

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
        <h1 className="text-3xl font-bold mb-2">Dispensing Money</h1>
        <p className="text-xl">Please wait...</p>
      </motion.div>
    </div>
  );
}
