import { useForexTransaction } from "../../hooks/useForexTransaction";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import Button from "../../components/common/Button";
import { ExchangeRateCard, CurrencyAmountGrid } from "../../components/forex";
import { ROUTES, getForexRoute } from "../../constants/routes";
import { useForex } from "../../context/ForexContext";
import { isForeignToPhp } from "../../constants/forexData";


export default function ExchangeRateScreen() {
  const navigate = useNavigate();
  const { forex, setSelectedAmount, getForexConfig } = useForex();
  const config = getForexConfig();
  const { availability, isOnline, isLoading, error, fetchedAt } = useForexTransaction();
  if (!config) {
    navigate(ROUTES.FOREX);
    return null;
  }

  const handleProceed = () => {
    if (forex.selectedAmount) {
      navigate(getForexRoute(ROUTES.FOREX_CONFIRM, forex.serviceType));
    }
  };

  const handleBack = () => {
    navigate(ROUTES.FOREX_REMINDER);
  };

  // Determine which currency to show for selection
  const selectionCurrency = isForeignToPhp(forex.serviceType)
    ? forex.fromCurrency // For foreign→PHP: select foreign amount
    : forex.toCurrency; // For PHP→foreign: select foreign amount to receive

  const choices = availability[forex.serviceType] || [];
  const disabledAmounts = (config.amountOptions || []).filter(amount => !choices.some(c => c.amount === amount && c.available));
  const warningMessage = error || (!isOnline ? "Forex requires an internet connection and valid rates." : choices.filter(c => !c.available).map(c => `${c.amount}: ${c.reason}`).join("; "));

  // Get the label for selection
  const selectionLabel = isForeignToPhp(forex.serviceType)
    ? "Select Specific Amount"
    : config.selectLabel || `Select ${forex.toCurrency} to Dispense`;

  // Determine rate display
  const rateDisplay = isForeignToPhp(forex.serviceType)
    ? forex.exchangeRate
    : forex.exchangeRate;

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: handleBack,
        subtitle: "Foreign Exchange",
        showClock: true,
      }}
    >
      <div className="flex flex-col items-center py-8 px-4">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-6"
        >
          <p className="text-coinnect-forex text-lg mb-1">Foreign Exchange</p>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Live Foreign Currency Exchange Rates
          </h1>
          <p className="text-coinnect-forex text-sm">
            Rates refresh hourly. {fetchedAt ? `Last fetched: ${new Date(fetchedAt + "Z").toLocaleString()}` : "Loading rates…"}
          </p>
        </motion.div>

        {/* Exchange Rate Card */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="w-full max-w-xl mb-8"
        >
          <ExchangeRateCard
            flag={config.flag}
            countryName={config.countryName}
            currencyCode={
              isForeignToPhp(forex.serviceType)
                ? forex.fromCurrency
                : forex.fromCurrency
            }
            rate={rateDisplay}
            targetCurrency={forex.toCurrency}
          />
        </motion.div>

        {/* Selection Label */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="text-xl font-semibold text-gray-800 mb-4"
        >
          {selectionLabel}
        </motion.p>

        {/* Amount Selection Grid */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="w-full max-w-md mb-8"
        >
          {warningMessage && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 text-amber-700 rounded-lg text-sm font-semibold text-center">
              {warningMessage}
            </div>
          )}
          <CurrencyAmountGrid
            amounts={config.amountOptions}
            currency={selectionCurrency}
            selectedAmount={forex.selectedAmount}
            onSelect={amount => setSelectedAmount(amount).catch(() => {})}
            disabledAmounts={disabledAmounts}
          />
        </motion.div>

        {/* Proceed Button */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Button
            variant="primary"
            size="xl"
            onClick={handleProceed}
            disabled={isLoading || !forex.selectedAmount || disabledAmounts.includes(forex.selectedAmount)}
            className="min-w-[200px] !bg-coinnect-forex hover:!bg-coinnect-forex/90 !text-white"
          >
            Proceed
          </Button>
        </motion.div>
      </div>
    </PageLayout>
  );
}
