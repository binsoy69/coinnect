import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import Button from '../../components/common/Button';
import { ROUTES, getForexRoute } from '../../constants/routes';
import { useForex } from '../../context/ForexContext';
import { formatCurrency, isForeignToPhp } from '../../constants/forexData';

export default function ForexSummaryScreen() {
  const navigate = useNavigate();
  const { forex, getForexConfig } = useForex();
  const config = getForexConfig();

  if (!config) {
    navigate(ROUTES.FOREX);
    return null;
  }

  const handleProceed = () => {
    navigate(getForexRoute(ROUTES.FOREX_PROCESSING, forex.serviceType));
  };

  const handleBack = () => {
    navigate(getForexRoute(ROUTES.FOREX_CONVERSION, forex.serviceType));
  };

  const isForeignIn = isForeignToPhp(forex.serviceType);

  // Display values
  const moneyInserted = isForeignIn
    ? formatCurrency(forex.moneyInserted, forex.fromCurrency)
    : `P${forex.moneyInserted}`;

  const convertedAmount = isForeignIn
    ? `P${forex.convertedAmount}`
    : formatCurrency(forex.convertedAmount, forex.toCurrency);

  const transactionFee = `P${forex.feeAmount}`;

  const moneyToDispense = isForeignIn
    ? `P${forex.amountToDispense}`
    : formatCurrency(forex.amountToDispense, forex.toCurrency);

  return (
    <div className="min-h-screen bg-surface-light flex items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-coinnect-forex rounded-card p-8 w-full max-w-lg text-white"
      >
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold italic mb-1">MY TRANSACTION</h1>
          <p className="text-sm opacity-80">Please review the information below</p>
        </div>

        {/* Transaction Details */}
        <div className="space-y-4 mb-8">
          {/* Transaction Type */}
          <div className="text-center">
            <p className="text-sm opacity-80 mb-1">Transaction Type</p>
            <p className="text-xl font-bold">Foreign Exchange</p>
          </div>

          {/* Service Type */}
          <div className="text-center">
            <p className="text-sm opacity-80 mb-1">Service Type</p>
            <p className="text-xl font-bold">{config.name}</p>
          </div>

          {/* Grid for amounts */}
          <div className="grid grid-cols-2 gap-4 mt-6">
            {/* Money Inserted */}
            <div className="text-center">
              <p className="text-sm opacity-80 mb-1">Total Money Inserted</p>
              <p className="text-3xl font-bold">{moneyInserted}</p>
            </div>

            {/* Converted Amount */}
            <div className="text-center">
              <p className="text-sm opacity-80 mb-1">Converted Amount</p>
              <p className="text-3xl font-bold">{convertedAmount}</p>
            </div>

            {/* Transaction Fee */}
            <div className="text-center">
              <p className="text-sm opacity-80 mb-1">Transaction Fee</p>
              <p className="text-3xl font-bold">{transactionFee}</p>
            </div>

            {/* Money to Dispense */}
            <div className="text-center">
              <p className="text-sm opacity-80 mb-1">Money to Dispensed</p>
              <p className="text-3xl font-bold">{moneyToDispense}</p>
            </div>
          </div>
        </div>

        {/* Buttons */}
        <div className="flex gap-4 justify-center">
          <Button
            variant="ghost"
            size="lg"
            onClick={handleBack}
            className="bg-white/20 text-white hover:bg-white/30 min-w-[140px]"
          >
            Back
          </Button>
          <Button
            variant="outline"
            size="lg"
            onClick={handleProceed}
            className="bg-white text-coinnect-forex hover:bg-gray-100 min-w-[140px]"
          >
            Proceed
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
