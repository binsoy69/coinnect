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
  const [errorMsg, setErrorMsg] = useState(null);

  const handleBack = () => {
    navigate(getServiceRoute(ROUTES.TRANSACTION_FEE, type));
  };

  const handleProceed = async () => {
    setIsStarting(true);
    setErrorMsg(null);
    try {
      // Start backend transaction before navigating to insert screen
      await startBackendTransaction(
        type,
        transaction.selectedAmount,
        transaction.fee,
        transaction.selectedDispenseDenominations
      );
      navigate(getServiceRoute(ROUTES.INSERT_MONEY, type));
    } catch (err) {
      setErrorMsg(err.message || "Failed to start transaction. Please check machine inventory and try again.");
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

      {errorMsg && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center p-4 z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl text-center border border-gray-100"
          >
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            
            <h3 className="text-2xl font-bold text-gray-900 mb-3">
              Transaction Error
            </h3>
            
            <p className="text-gray-600 mb-8 leading-relaxed">
              {errorMsg}
            </p>
            
            <div className="flex gap-4">
              <Button
                variant="outline"
                size="lg"
                onClick={() => setErrorMsg(null)}
                className="flex-1 text-gray-700 border-gray-300"
              >
                Close
              </Button>
              <Button
                variant="primary"
                size="lg"
                onClick={() => navigate(ROUTES.HOME)}
                className="flex-1 bg-coinnect-primary text-white"
              >
                Home
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </PageTransition>
  );
}
