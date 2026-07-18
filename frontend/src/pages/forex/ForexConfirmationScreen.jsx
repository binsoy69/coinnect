import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { HelpCircle } from "lucide-react";
import Button from "../../components/common/Button";
import { ROUTES, getForexRoute } from "../../constants/routes";
import { useForex } from "../../context/ForexContext";
import { formatCurrency, isForeignToPhp } from "../../constants/forexData";
import { useForexTransaction } from "../../hooks/useForexTransaction";

export default function ForexConfirmationScreen() {
  const navigate = useNavigate();
  const { forex, lockRate, getForexConfig } = useForex();
  const { startForexBackendTransaction } = useForexTransaction();
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const config = getForexConfig();

  if (!config) {
    navigate(ROUTES.FOREX);
    return null;
  }

  const handleProceed = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      await startForexBackendTransaction(
        forex.serviceType,
        forex.selectedAmount,
        []
      );
      lockRate();
      navigate(getForexRoute(ROUTES.FOREX_INSERT, forex.serviceType));
    } catch (err) {
      setErrorMsg(err.message || "Failed to start forex transaction. Please check machine inventory and try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    navigate(getForexRoute(ROUTES.FOREX_RATE, forex.serviceType));
  };

  // Determine display values based on direction
  const isForeignIn = isForeignToPhp(forex.serviceType);

  const amountSelected = isForeignIn
    ? formatCurrency(forex.selectedAmount, forex.fromCurrency)
    : formatCurrency(forex.selectedAmount, forex.toCurrency);

  const amountConverted = isForeignIn
    ? `P${forex.convertedAmount}`
    : `P${forex.convertedAmount}`;

  const transactionFee = `P${forex.feeAmount}`;

  const amountToDispense = isForeignIn
    ? `P${forex.amountToDispense}`
    : formatCurrency(forex.amountToDispense, forex.toCurrency);

  // For PHP→Foreign, show Total Due instead of Amount to Dispense
  const displayLabel = isForeignIn ? "Amount to Dispense" : "Total Due";
  const displayValue = isForeignIn ? amountToDispense : `P${forex.totalDue}`;

  return (
    <div className="min-h-screen bg-coinnect-forex flex flex-col items-center justify-center p-8">
      {/* Question Mark Icon */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.3 }}
        className="mb-8"
      >
        <div className="w-32 h-32 rounded-full border-4 border-white flex items-center justify-center">
          <HelpCircle className="w-20 h-20 text-white" strokeWidth={1.5} />
        </div>
      </motion.div>

      {/* Confirmation Details */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="text-center text-white mb-8"
      >
        <p className="text-xl mb-4">
          <span className="font-normal">Amount Selected: </span>
          <span className="font-bold">{amountSelected}</span>
          <span className="mx-2">|</span>
          <span className="font-normal">Amount Converted: </span>
          <span className="font-bold">{amountConverted}</span>
        </p>
        <p className="text-xl mb-4">
          <span className="font-normal">Transaction Fee: </span>
          <span className="font-bold">{transactionFee}</span>
          <span className="mx-2">|</span>
          <span className="font-normal">{displayLabel}: </span>
          <span className="font-bold">{displayValue}</span>
        </p>
        <p className="text-xl font-semibold">
          Click <span className="font-bold">Proceed</span> to Continue.
        </p>
      </motion.div>

      {/* Buttons */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="flex gap-4"
      >
        <Button
          variant="outline"
          size="xl"
          onClick={handleBack}
          className="min-w-[150px]"
        >
          Back
        </Button>
        <Button
          variant="white"
          size="xl"
          onClick={handleProceed}
          disabled={loading}
          className="min-w-[150px] !text-coinnect-forex"
        >
          {loading ? "Loading..." : "Proceed"}
        </Button>
      </motion.div>

      {/* Note */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="text-white/80 text-sm mt-8"
      >
        <span className="font-bold">Note:</span> The transaction fee is
        automatically deducted from the inserted amount.
      </motion.p>

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
    </div>
  );
}
