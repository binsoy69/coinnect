import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { HelpCircle } from 'lucide-react';
import Button from '../../components/common/Button';
import { ROUTES, getForexRoute } from '../../constants/routes';
import { useForex } from '../../context/ForexContext';
import { formatCurrency, isForeignToPhp } from '../../constants/forexData';

export default function ForexConfirmationScreen() {
  const navigate = useNavigate();
  const { forex, lockRate, getForexConfig } = useForex();
  const config = getForexConfig();

  if (!config) {
    navigate(ROUTES.FOREX);
    return null;
  }

  const handleProceed = () => {
    // Lock the rate when user confirms
    lockRate();
    navigate(getForexRoute(ROUTES.FOREX_INSERT, forex.serviceType));
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
  const displayLabel = isForeignIn ? 'Amount to Dispense' : 'Total Due';
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
          className="bg-white text-coinnect-forex hover:bg-gray-100 min-w-[150px]"
        >
          Back
        </Button>
        <Button
          variant="outline"
          size="xl"
          onClick={handleProceed}
          className="bg-transparent border-white text-white hover:bg-white/10 min-w-[150px]"
        >
          Proceed
        </Button>
      </motion.div>

      {/* Note */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="text-white/80 text-sm mt-8"
      >
        <span className="font-bold">Note:</span> The transaction fee is automatically deducted from the inserted amount.
      </motion.p>
    </div>
  );
}
