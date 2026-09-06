import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import Button from "../../components/common/Button";
import Clock from "../../components/common/Clock";
import { ExchangeRateCard, ConversionDisplay } from "../../components/forex";
import { ROUTES, getForexRoute } from "../../constants/routes";
import { useForex } from "../../context/ForexContext";
import { isForeignToPhp } from "../../constants/forexData";

export default function ForexConversionScreen() {
  const navigate = useNavigate();
  const { forex, getForexConfig, backendState } = useForex();
  const config = getForexConfig();

  useEffect(() => {
    if (["CLAIM_REQUIRED", "ERROR", "CANCELLED"].includes(backendState?.state)) navigate(getForexRoute(ROUTES.FOREX_WARNING, forex.serviceType));
  }, [backendState?.state, navigate, forex.serviceType]);

  if (!config) {
    navigate(ROUTES.FOREX);
    return null;
  }

  const handleProceed = () => {
    navigate(getForexRoute(ROUTES.FOREX_SUMMARY, forex.serviceType));
  };

  const isForeignIn = isForeignToPhp(forex.serviceType);
  const insertedAmount = forex.moneyInserted;
  const convertedAmount = forex.convertedAmount;
  const fromCurrency = isForeignIn ? forex.fromCurrency : forex.toCurrency;
  const toCurrency = "PHP";
  if (!forex.selectedAmount) return <p>Restoring transaction…</p>;

  // Header subtitle
  const headerSubtitle = `${config.name} Conversion`;

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: () =>
          navigate(getForexRoute(ROUTES.FOREX_INSERT, forex.serviceType)),
        subtitle: headerSubtitle,
        rightContent: (
          <div className="flex items-center gap-2 bg-coinnect-forex text-white px-3 py-1 rounded-full text-sm">
            <span className="w-2 h-2 bg-white rounded-full"></span>
            Foreign Exchange
          </div>
        ),
      }}
    >
      <div className="flex gap-6 p-6 min-h-[calc(100vh-140px)]">
        {/* Left Panel - Summary Card */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="w-1/3"
        >
          <div className="bg-coinnect-forex rounded-card p-6 text-white">
            <div className="mb-6">
              <p className="text-sm opacity-80 mb-1">Money Inserted</p>
              <p className="text-4xl font-bold">
                {isForeignIn
                  ? `${config.fromSymbol}${insertedAmount}`
                  : `P${insertedAmount}`}
              </p>
            </div>

            <div className="mb-6">
              <p className="text-sm opacity-80 mb-1">Transaction Fee</p>
              <p className="text-2xl font-bold">P{forex.feeAmount}</p>
            </div>

            <div className="pt-4 border-t border-white/20">
              <Clock variant="light" showDate={true} />
            </div>
          </div>
        </motion.div>

        {/* Right Panel - Conversion Details */}
        <div className="flex-1 flex flex-col">
          {/* Heading */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-4"
          >
            <h2 className="text-xl font-bold text-gray-900">
              Live {isForeignIn ? forex.fromCurrency : forex.toCurrency}{" "}
              Currency Exchange Rates
            </h2>
            <p className="text-gray-500 text-sm">
              The confirmed rate is locked for this transaction.
            </p>
          </motion.div>

          {/* Exchange Rate Card */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-6"
          >
            <ExchangeRateCard
              flag={config.flag}
              countryName={config.countryName}
              currencyCode={isForeignIn ? forex.fromCurrency : "PHP"}
              rate={forex.exchangeRate}
              targetCurrency={forex.toCurrency}
            />
          </motion.div>

          {/* Conversion Section */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mb-6"
          >
            <h3 className="text-lg font-semibold text-gray-800 mb-1">
              Conversion (Transaction Fee not included)
            </h3>
            <p className="text-gray-500 text-sm mb-3">
              Centavos are not included for dispensing.
            </p>

            <ConversionDisplay
              fromAmount={forex.selectedAmount}
              fromCurrency={fromCurrency}
              toAmount={convertedAmount}
              toCurrency={toCurrency}
              showHeader={true}
              note=""
            />
          </motion.div>

          {/* Proceed Button */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-auto flex justify-end"
          >
            <Button
              variant="primary"
              size="xl"
              onClick={handleProceed}
              className="min-w-[200px] !bg-coinnect-forex hover:!bg-coinnect-forex/90"
            >
              Proceed
            </Button>
          </motion.div>
        </div>
      </div>
    </PageLayout>
  );
}
