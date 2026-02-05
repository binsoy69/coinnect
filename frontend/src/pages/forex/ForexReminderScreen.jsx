import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import Button from '../../components/common/Button';
import { ROUTES, getForexRoute } from '../../constants/routes';
import { useForex } from '../../context/ForexContext';

export default function ForexReminderScreen() {
  const navigate = useNavigate();
  const { forex } = useForex();
  const serviceType = forex.serviceType;

  const handleProceed = () => {
    navigate(getForexRoute(ROUTES.FOREX_RATE, serviceType));
  };

  return (
    <div className="min-h-screen bg-coinnect-forex flex flex-col items-center justify-center p-8">
      {/* Kiosk Icon */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <svg
          width="120"
          height="120"
          viewBox="0 0 120 120"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="text-white"
        >
          {/* Kiosk body */}
          <rect
            x="20"
            y="20"
            width="80"
            height="70"
            rx="8"
            stroke="currentColor"
            strokeWidth="4"
            fill="none"
          />
          {/* Screen */}
          <rect
            x="30"
            y="30"
            width="60"
            height="40"
            rx="4"
            stroke="currentColor"
            strokeWidth="3"
            fill="none"
          />
          {/* Smiley face */}
          <circle cx="45" cy="45" r="4" fill="currentColor" />
          <circle cx="75" cy="45" r="4" fill="currentColor" />
          <path
            d="M45 55 Q60 65 75 55"
            stroke="currentColor"
            strokeWidth="3"
            fill="none"
            strokeLinecap="round"
          />
          {/* Receipt slot */}
          <rect x="40" y="75" width="40" height="8" rx="2" fill="currentColor" />
          {/* Stand */}
          <rect x="55" y="90" width="10" height="20" fill="currentColor" />
          <rect x="45" y="105" width="30" height="5" rx="2" fill="currentColor" />
        </svg>
      </motion.div>

      {/* Reminder Text */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="text-center text-white max-w-lg"
      >
        <h1 className="text-2xl font-bold mb-4">REMINDER:</h1>
        <p className="text-lg leading-relaxed mb-2">
          Once you insert money, it cannot be refunded unless
        </p>
        <p className="text-lg leading-relaxed mb-2">
          affected by unforeseen circumstances
        </p>
        <p className="text-lg leading-relaxed mb-4">
          beyond human error.
        </p>
        <p className="text-xl font-bold uppercase">
          PLEASE REVIEW YOUR TRANSACTION CAREFULLY.
        </p>
      </motion.div>

      {/* Proceed Button */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="mt-10"
      >
        <Button
          variant="outline"
          size="xl"
          onClick={handleProceed}
          className="bg-transparent border-white text-white hover:bg-white/10 min-w-[200px]"
        >
          Proceed
        </Button>
      </motion.div>
    </div>
  );
}
