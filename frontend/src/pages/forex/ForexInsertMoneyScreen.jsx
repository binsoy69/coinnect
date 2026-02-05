import { useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import InsertMoneyPanel from "../../components/transaction/InsertMoneyPanel";
import Timer from "../../components/common/Timer";
import { ROUTES, getForexRoute } from "../../constants/routes";
import { useForex } from "../../context/ForexContext";
import {
  formatCurrency,
  isForeignToPhp,
  FOREX_TIMER_DURATIONS,
} from "../../constants/forexData";

export default function ForexInsertMoneyScreen() {
  const navigate = useNavigate();
  const { forex, addInsertedMoney, getForexConfig, isAmountMatched } =
    useForex();
  const config = getForexConfig();

  // Handle timeout - go to warning or conversion screen
  const handleTimeout = useCallback(() => {
    if (isAmountMatched()) {
      navigate(getForexRoute(ROUTES.FOREX_CONVERSION, forex.serviceType));
    } else {
      navigate(getForexRoute(ROUTES.FOREX_WARNING, forex.serviceType));
    }
  }, [navigate, forex.serviceType, isAmountMatched]);

  // Keyboard simulation for testing
  useEffect(() => {
    if (!config) return;

    const handleKeyPress = (e) => {
      const acceptDenoms = config.acceptDenominations;
      const keyMap = {
        1: acceptDenoms[0],
        2: acceptDenoms[1],
        3: acceptDenoms[2],
        4: acceptDenoms[3],
        5: acceptDenoms[4],
        6: acceptDenoms[5],
      };

      if (keyMap[e.key]) {
        addInsertedMoney(keyMap[e.key]);
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [config, addInsertedMoney]);

  // Auto-advance when amount is matched
  useEffect(() => {
    if (isAmountMatched()) {
      const timer = setTimeout(() => {
        navigate(getForexRoute(ROUTES.FOREX_CONVERSION, forex.serviceType));
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [forex.moneyInserted, isAmountMatched, navigate, forex.serviceType]);

  if (!config) {
    navigate(ROUTES.FOREX);
    return null;
  }

  const isForeignIn = isForeignToPhp(forex.serviceType);

  // Determine denominations
  const acceptedDenoms = config.acceptDenominations;

  // Current count display
  const currentCount = isForeignIn
    ? formatCurrency(forex.moneyInserted, forex.fromCurrency)
    : `P${forex.moneyInserted}`;

  // Total due display
  const totalDue = isForeignIn
    ? formatCurrency(forex.selectedAmount, forex.fromCurrency)
    : `P${forex.totalDue}`;

  // Header subtitle
  const headerSubtitle = `${config.name} Conversion`;

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: () =>
          navigate(getForexRoute(ROUTES.FOREX_CONFIRM, forex.serviceType)),
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
        {/* Left Panel - Instructions */}
        <div className="w-1/3">
          <InsertMoneyPanel
            variant="bill"
            cardVariant="forex"
            noteText={config.insertNote}
          />
        </div>

        {/* Right Panel - Counter */}
        <div className="flex-1 flex flex-col">
          {/* Heading */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center mb-6"
          >
            <h1 className="text-2xl font-bold text-coinnect-forex mb-1">
              {config.insertHeading}
            </h1>
            {config.acceptedDenomNote && (
              <p className="text-coinnect-forex text-sm">
                {config.acceptedDenomNote}
              </p>
            )}
          </motion.div>

          {/* Current Count */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 }}
            className="text-center mb-4"
          >
            <p className="text-lg text-gray-600 mb-1">Current Count</p>
            <p className="text-6xl font-bold text-gray-900">{currentCount}</p>
          </motion.div>

          {/* Total Due Badge */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="flex justify-center mb-6"
          >
            <span className="bg-coinnect-forex text-white px-4 py-2 rounded-full text-lg font-semibold">
              Total Due: {totalDue}
            </span>
          </motion.div>

          {/* Denomination Counters */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex justify-center gap-4 flex-wrap mb-6"
          >
            {acceptedDenoms.map((denom) => {
              const count = forex.insertedCounts[denom] || 0;
              const symbol = isForeignIn ? config.fromSymbol : "P";
              return (
                <div
                  key={denom}
                  className="text-center bg-gray-100 px-4 py-2 rounded-lg"
                >
                  <span className="text-lg font-semibold text-coinnect-forex">
                    {symbol}
                    {denom}
                  </span>
                  <span className="text-gray-600 ml-2">= {count}x</span>
                </div>
              );
            })}
          </motion.div>

          {/* Timer */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mt-auto"
          >
            <Timer
              seconds={FOREX_TIMER_DURATIONS.INSERT_MONEY}
              onComplete={handleTimeout}
              showProgressBar={true}
              autoStart={true}
              color="forex"
            />
            <p className="text-center text-gray-500 text-sm mt-2">
              This tab will automatically close after 60s if no money is
              inserted.
            </p>
          </motion.div>
        </div>
      </div>
    </PageLayout>
  );
}
