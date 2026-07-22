import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import Button from '../../components/common/Button';
import WarningIcon from '../../components/feedback/WarningIcon';
import PageTransition from '../../components/layout/PageTransition';
import { ROUTES, getServiceRoute } from '../../constants/routes';
import { useBackendTransaction } from '../../hooks/useBackendTransaction';
import { formatPeso } from '../../constants/denominations';

export default function WarningScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { backendState, cancelBackendTransaction, transactionId } = useBackendTransaction();

  useEffect(() => {
    if (backendState?.state === "COMPLETE") {
      navigate(getServiceRoute(ROUTES.SUCCESS, type));
    }
  }, [backendState, navigate, type]);

  const claimTicket = backendState?.claim_ticket_code;
  const shortfall = backendState?.shortfall;
  const isDispenseError =
    backendState?.state === "ERROR" || Boolean(claimTicket) || shortfall != null;

  const handleChooseDifferent = async () => {
    if (transactionId) {
      try {
        await cancelBackendTransaction();
      } catch {
        // Navigation still lets the user recover if backend cancellation fails.
      }
    }
    navigate(getServiceRoute(ROUTES.SELECT_AMOUNT, type));
  };

  const handleInsertMore = () => {
    navigate(getServiceRoute(ROUTES.INSERT_MONEY, type));
  };

  const handleReturnHome = () => {
    navigate(ROUTES.HOME);
  };

  if (isDispenseError) {
    return (
      <PageTransition>
        <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-8">
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
              Dispense Error & Assistance Required
            </motion.h1>

            <p className="text-white/80 text-base mb-6">
              {backendState?.error_message ||
                "A hardware issue occurred while dispensing your cash."}
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
                    {formatPeso(shortfall)}
                  </span>
                </div>
              )}

              {backendState?.dispensed_amount != null && (
                <div className="flex justify-between items-center text-sm py-1">
                  <span className="text-white/70">Dispensed:</span>
                  <span className="font-semibold text-white">
                    {formatPeso(backendState.dispensed_amount)}
                  </span>
                </div>
              )}

              <p className="text-xs text-white/70 mt-4 text-center">
                Please present this reference code or your printed receipt to the kiosk administrator to claim your remaining cash.
              </p>
            </motion.div>

            {/* Action button */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
            >
              <Button
                variant="white"
                size="xl"
                onClick={handleReturnHome}
                className="px-12"
              >
                Return to Home
              </Button>
            </motion.div>
          </motion.div>
        </div>
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center text-white max-w-2xl"
        >
          {/* Warning icon */}
          <div className="flex justify-center mb-8">
            <WarningIcon size={160} />
          </div>

          {/* Warning message */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-3xl font-bold mb-12 leading-relaxed"
          >
            The total amount you inserted does not match the selected transaction.
          </motion.h1>

          {/* Action buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex flex-col sm:flex-row justify-center gap-4"
          >
            <Button
              variant="outline"
              size="xl"
              onClick={handleChooseDifferent}
              className="bg-transparent border-white text-white hover:bg-white/10 px-8"
            >
              Choose a Different Amount
            </Button>
            <Button
              variant="white"
              size="xl"
              onClick={handleInsertMore}
              className="px-8"
            >
              Insert More Money
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </PageTransition>
  );
}
