import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import Button from '../../components/common/Button';
import WarningIcon from '../../components/feedback/WarningIcon';
import PageTransition from '../../components/layout/PageTransition';
import { ROUTES, getServiceRoute } from '../../constants/routes';
import { useTransaction } from '../../context/TransactionContext';
import { useBackendTransaction } from '../../hooks/useBackendTransaction';
import { formatPeso } from '../../constants/denominations';

export default function WarningScreen() {
  const navigate = useNavigate();
  const { resetTransaction } = useTransaction();
  const { type } = useParams();
  const {
    backendState,
    refreshBackendTransaction,
    transactionId,
  } = useBackendTransaction();
  const [isChecking, setIsChecking] = useState(Boolean(transactionId));
  const [statusError, setStatusError] = useState(
    transactionId ? null : "Missing transaction reference"
  );

  useEffect(() => {
    let cancelled = false;
    let pollTimer;
    if (!transactionId) {
      return undefined;
    }
    const check = async () => {
      try {
        const data = await refreshBackendTransaction();
        if (cancelled) return;
        if (data?.state === "COMPLETE") {
          navigate(getServiceRoute(ROUTES.SUCCESS, type), { replace: true });
          return;
        }
        if (["CLAIM_REQUIRED", "ERROR", "CANCELLED"].includes(data?.state)) {
          setIsChecking(false);
          return;
        }
        pollTimer = window.setTimeout(check, 1000);
      } catch (err) {
        if (!cancelled) {
          setStatusError(err.message);
          setIsChecking(false);
        }
      }
    };
    check();
    return () => {
      cancelled = true;
      if (pollTimer) window.clearTimeout(pollTimer);
    };
  }, [navigate, refreshBackendTransaction, transactionId, type]);

  const claimTicket = backendState?.claim_ticket_code;
  const shortfall = backendState?.claim?.amount ?? backendState?.shortfall;
  const isDispenseError =
    backendState?.state === "ERROR" || Boolean(claimTicket) || shortfall != null;
  const isNonTerminal =
    backendState?.state === "DISPENSING" ||
    backendState?.state === "WAITING_FOR_CONFIRMATION";

  const handleInsertMore = () => {
    navigate(getServiceRoute(ROUTES.INSERT_MONEY, type));
  };

  const handleReturnHome = () => {
    if (["COMPLETE", "CLAIM_REQUIRED", "ERROR", "CANCELLED"].includes(backendState?.state)) resetTransaction();
    navigate(ROUTES.HOME);
  };

  if (isChecking || isNonTerminal) {
    return (
      <PageTransition>
        <div className="min-h-screen bg-coinnect-primary flex items-center justify-center p-8">
          <p className="text-white text-2xl font-semibold text-center">
            Checking the final transaction status. Please wait…
          </p>
        </div>
      </PageTransition>
    );
  }

  if (statusError) {
    return (
      <PageTransition>
        <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-8 text-center text-white">
          <WarningIcon size={140} />
          <h1 className="text-3xl font-bold mt-6 mb-3">
            Transaction Status Unavailable
          </h1>
          <p className="text-white/80 max-w-xl mb-8">
            We could not verify the final transaction status. Please keep any
            printed ticket and contact the kiosk administrator.
          </p>
          <Button variant="white" size="xl" onClick={handleReturnHome}>
            Return to Home
          </Button>
        </div>
      </PageTransition>
    );
  }

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
              variant="white"
              size="xl"
              onClick={backendState?.can_continue ? handleInsertMore : handleReturnHome}
              className="px-8"
            >
              {backendState?.can_continue ? "Insert More Money" : "Return to Home"}
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </PageTransition>
  );
}
