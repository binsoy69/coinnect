import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import WarningIcon from '../../components/feedback/WarningIcon';
import Button from '../../components/common/Button';
import { ROUTES, getForexRoute } from '../../constants/routes';
import { useForex } from '../../context/ForexContext';

export default function ForexWarningScreen() {
  const navigate = useNavigate();
  const { forex } = useForex();

  const handleChooseDifferent = () => {
    navigate(getForexRoute(ROUTES.FOREX_RATE, forex.serviceType));
  };

  const handleInsertMore = () => {
    navigate(getForexRoute(ROUTES.FOREX_INSERT, forex.serviceType));
  };

  return (
    <div className="min-h-screen bg-coinnect-forex flex flex-col items-center justify-center p-8">
      {/* Warning Icon */}
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: 'spring', duration: 0.5 }}
        className="mb-8"
      >
        <WarningIcon size={150} />
      </motion.div>

      {/* Warning Message */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="text-center text-white mb-10 max-w-md"
      >
        <h1 className="text-2xl font-bold leading-relaxed">
          The total amount you inserted does not match
          <br />
          the selected transaction.
        </h1>
      </motion.div>

      {/* Buttons */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="flex gap-4"
      >
        <Button
          variant="outline"
          size="xl"
          onClick={handleChooseDifferent}
          className="bg-transparent border-white text-white hover:bg-white/10 min-w-[220px]"
        >
          Choose a Different Amount
        </Button>
        <Button
          variant="outline"
          size="xl"
          onClick={handleInsertMore}
          className="bg-white text-coinnect-forex hover:bg-gray-100 min-w-[180px]"
        >
          Insert More Money
        </Button>
      </motion.div>
    </div>
  );
}
