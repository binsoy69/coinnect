import { useNavigate, useParams } from "react-router-dom";
import { useState } from "react";
import { motion } from "framer-motion";
import Button from "../../components/common/Button";
import PageTransition from "../../components/layout/PageTransition";
import { ROUTES, getServiceRoute } from "../../constants/routes";
import { useTransaction } from "../../context/TransactionContext";
import { useBackendTransaction } from "../../hooks/useBackendTransaction";
import { formatPeso } from "../../constants/denominations";

// Question mark icon
const QuestionIcon = () => (
  <div className="w-20 h-20 mx-auto mb-4 rounded-full border-4 border-white flex items-center justify-center">
    <span className="text-4xl font-bold text-white">?</span>
  </div>
);

export default function ConfirmationScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { transaction } = useTransaction();
  const { startBackendTransaction } = useBackendTransaction();
  const [isStarting, setIsStarting] = useState(false);

  const handleBack = () => {
    navigate(getServiceRoute(ROUTES.TRANSACTION_FEE, type));
  };

  const handleProceed = async () => {
    setIsStarting(true);
    try {
      // Start backend transaction before navigating to insert screen
      await startBackendTransaction(
        type,
        transaction.selectedAmount,
        transaction.fee,
        transaction.selectedDispenseDenominations
      );
      navigate(getServiceRoute(ROUTES.INSERT_MONEY, type));
    } catch {
      // On error, still navigate (frontend can work in offline/demo mode)
      navigate(getServiceRoute(ROUTES.INSERT_MONEY, type));
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <PageTransition>
      <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center text-white max-w-2xl"
        >
          {/* Question icon */}
          <div className="transform scale-90">
            <QuestionIcon />
          </div>

          {/* Amount details */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-4"
          >
            <p className="text-xl">
              Amount Selected:{" "}
              <span className="font-bold">
                {formatPeso(transaction.selectedAmount || 0)}
              </span>
              {" | "}
              Transaction Fee:{" "}
              <span className="font-bold">{formatPeso(transaction.fee)}</span>
            </p>
          </motion.div>

          {/* Total Due */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mb-6"
          >
            <p className="text-3xl font-bold">
              Total Due: {formatPeso(transaction.totalDue)}
            </p>
          </motion.div>

          {/* Instruction */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-lg mb-8 text-white/90"
          >
            Click Proceed to Continue.
          </motion.p>

          {/* Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex gap-6 justify-center"
          >
            <Button
              variant="outline"
              size="xl"
              onClick={handleBack}
              className="px-12"
            >
              Back
            </Button>
            <Button
              variant="white"
              size="xl"
              onClick={handleProceed}
              className="px-12"
              disabled={isStarting}
            >
              {isStarting ? "Starting..." : "Proceed"}
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </PageTransition>
  );
}
