import { useNavigate, useParams } from "react-router-dom";
import { useEffect, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import InsertMoneyPanel from "../../components/transaction/InsertMoneyPanel";
import MoneyCounter from "../../components/transaction/MoneyCounter";
import Timer from "../../components/common/Timer";
import Button from "../../components/common/Button";
import { ROUTES, getServiceRoute } from "../../constants/routes";
import {
  SERVICE_CONFIG,
  TRANSACTION_TYPE_LABEL,
  TIMER_DURATIONS,
} from "../../constants/mockData";
import { useTransaction } from "../../context/TransactionContext";
import { formatPeso } from "../../constants/denominations";

// Service type indicator component
function ServiceIndicator({ icon, shortName }) {
  return (
    <div className="flex items-center gap-2 bg-coinnect-primary/10 rounded-full px-4 py-2">
      <img src={icon} alt="" className="w-6 h-6" />
      <span className="text-coinnect-primary font-semibold text-sm">
        {shortName}
      </span>
    </div>
  );
}

export default function InsertMoneyScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { transaction, addInsertedMoney, getServiceConfig, isAmountMatched } =
    useTransaction();

  const config = getServiceConfig() || SERVICE_CONFIG[type];

  // Simulate money insertion for demo (press keys 1-4 to insert different denominations)
  useEffect(() => {
    const handleKeyPress = (e) => {
      const keyMap = {
        1: config?.insertCounters[0],
        2: config?.insertCounters[1],
        3: config?.insertCounters[2],
        4: config?.insertCounters[3],
      };

      if (keyMap[e.key]) {
        addInsertedMoney(keyMap[e.key]);
      }
    };

    window.addEventListener("keypress", handleKeyPress);
    return () => window.removeEventListener("keypress", handleKeyPress);
  }, [addInsertedMoney, config?.insertCounters]);

  const handleTimerComplete = useCallback(() => {
    // Auto-navigate when timer completes
    if (isAmountMatched()) {
      navigate(getServiceRoute(ROUTES.TRANSACTION_SUMMARY, type));
    } else {
      navigate(getServiceRoute(ROUTES.WARNING, type));
    }
  }, [navigate, type, isAmountMatched]);

  const handleProceed = () => {
    if (isAmountMatched()) {
      navigate(getServiceRoute(ROUTES.TRANSACTION_SUMMARY, type));
    } else {
      navigate(getServiceRoute(ROUTES.WARNING, type));
    }
  };

  // Build counts object for MoneyCounter
  const buildCounts = () => {
    const counts = {};
    config?.insertCounters?.forEach((denom) => {
      counts[denom] = transaction.insertedCounts[denom] || 0;
    });
    return counts;
  };

  const serviceIndicator = useMemo(
    () => (
      <ServiceIndicator icon={config?.icon} shortName={config?.shortName} />
    ),
    [config?.icon, config?.shortName],
  );

  return (
    <PageLayout
      headerProps={{
        showBack: false,
        subtitle: TRANSACTION_TYPE_LABEL,
        rightContent: serviceIndicator,
      }}
    >
      <div className="py-2 h-[calc(100vh-140px)]">
        <div className="flex flex-col md:flex-row gap-6 h-full">
          {/* Left panel - Insert instructions */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex-none w-full md:w-72"
          >
            <InsertMoneyPanel
              variant={config?.insertType || "bill"}
              noteText={config?.insertNote || ""}
              className="h-full"
            />
          </motion.div>

          {/* Right panel - Money counter and timer */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex-1 flex flex-col items-center text-center pt-2 justify-between"
          >
            <div>
              {/* Heading */}
              <h2 className="text-2xl font-bold text-coinnect-primary mb-1">
                {config?.insertHeading || "Please Insert Money"}
              </h2>

              {/* Current count label */}
              <p className="text-lg font-bold text-gray-900 mb-1">
                Current Count
              </p>

              {/* Large amount display */}
              <div className="text-7xl font-black text-gray-900 mb-4">
                {formatPeso(transaction.moneyInserted)}
              </div>

              {/* Amount to insert badge */}
              <div className="inline-flex border-2 border-coinnect-primary text-coinnect-primary rounded-xl px-6 py-2 mb-6 bg-white shadow-sm">
                <span className="text-lg font-bold">
                  {config?.insertType === "coin" ? "Coin" : "Bill"} to Insert:{" "}
                  {formatPeso(transaction.totalDue)}
                </span>
              </div>

              {/* Money counter */}
              <MoneyCounter
                counts={buildCounts()}
                denominations={config?.insertCounters}
                variant="horizontal"
                className="mb-4"
              />
            </div>

            {/* Timer */}
            <div className="w-full max-w-xl pb-2">
              <Timer
                seconds={TIMER_DURATIONS.INSERT_MONEY}
                onComplete={handleTimerComplete}
                showProgressBar={true}
              />

              <p className="text-center text-gray-400 text-xs mt-2">
                This tab will automatically close after{" "}
                {TIMER_DURATIONS.INSERT_MONEY}s if no money is inserted.
              </p>

              {/* Manual proceed button */}
              <Button
                variant="primary"
                size="lg"
                onClick={handleProceed}
                className="w-full mt-2"
                disabled={!isAmountMatched()}
              >
                Proceed
              </Button>
            </div>
          </motion.div>
        </div>
      </div>
    </PageLayout>
  );
}
