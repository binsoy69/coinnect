import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import WarningIcon from '../../components/feedback/WarningIcon';
import Button from '../../components/common/Button';
import { ROUTES, getForexRoute } from '../../constants/routes';
import { useForex } from '../../context/ForexContext';
import { useForexTransaction } from '../../hooks/useForexTransaction';

export default function ForexWarningScreen() {
  const navigate = useNavigate();
  const { forex } = useForex();
  const { cancelForexTransaction, transactionId, backendState } = useForexTransaction();

  const claimTicket = backendState?.claim_ticket_code;
  const shortfall = backendState?.shortfall;
  const isDispenseError =
    backendState?.state === "ERROR" || Boolean(claimTicket) || shortfall != null;

  const handleChooseDifferent = async () => {
    if (transactionId) {
      try {
        await cancelForexTransaction();
      } catch {
        // Navigation still lets the user recover if backend cancellation fails.
      }
    }
    navigate(getForexRoute(ROUTES.FOREX_RATE, forex.serviceType));
  };

  const handleInsertMore = () => {
    navigate(getForexRoute(ROUTES.FOREX_INSERT, forex.serviceType));
  };

  const handleReturnHome = () => {
    navigate(ROUTES.HOME);
  };

  if (isDispenseError) {
    return (
      <div className="min-h-screen bg-coinnect-forex flex flex-col items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center text-white max-w-2xl w-full"
        >
          {/* Warning Icon */}
          <div className="flex justify-center mb-6">
            <WarningIcon size={140} />
          </div>

          {/* Error Heading */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-3xl font-bold mb-3"
          >
            Forex Dispense Error & Assistance Required
          </motion.h1>

          <p className="text-white/80 text-base mb-6">
            {backendState?.error_message ||
              "A hardware issue occurred while dispensing your foreign exchange currency."}
          </p>

          {/* Claim Ticket Details Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-white/10 backdrop-blur-md rounded-2xl p-6 mb-8 border border-white/20 text-left max-w-md mx-auto"
          >
            <div className="text-center border-b border-white/20 pb-4 mb-4">
              <span className="text-xs uppercase tracking-wider text-white/70 block mb-1">
                Claim Ticket Reference
              </span>
              <span className="text-3xl font-mono font-bold tracking-widest text-amber-300">
                {claimTicket || "CLAIM-TICKET"}
              </span>
            </div>

            {shortfall != null && (
              <div className="flex justify-between items-center text-sm py-1">
                <span className="text-white/70">Shortfall Owed:</span>
                <span className="font-bold text-amber-300 text-lg">
                  {shortfall}
                </span>
              </div>
            )}

            <p className="text-xs text-white/70 mt-4 text-center">
              Please present this reference code or your printed receipt to the kiosk administrator to claim your remaining currency.
            </p>
          </motion.div>

          {/* Action button */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Button
              variant="outline"
              size="xl"
              onClick={handleReturnHome}
              className="bg-white text-coinnect-forex hover:bg-gray-100 px-12"
            >
              Return to Home
            </Button>
          </motion.div>
        </motion.div>
      </div>
    );
  }

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
