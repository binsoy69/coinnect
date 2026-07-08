import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import Button from "../../components/common/Button";
import { ExchangeRateCard, CurrencyAmountGrid } from "../../components/forex";
import { ROUTES, getForexRoute } from "../../constants/routes";
import { useForex } from "../../context/ForexContext";
import { isForeignToPhp, CURRENCY_SYMBOLS } from "../../constants/forexData";
import { API_BASE } from "../../constants/api";

export default function ExchangeRateScreen() {
  const navigate = useNavigate();
  const { forex, setSelectedAmount, getForexConfig } = useForex();
  const config = getForexConfig();
  const [inventory, setInventory] = useState(null);

  useEffect(() => {
    const fetchInventory = async () => {
      try {
        const resp = await fetch(`${API_BASE}/inventory`);
        if (resp.ok) {
          const data = await resp.json();
          setInventory(data);
        }
      } catch (err) {
        console.error("Error fetching inventory:", err);
      }
    };
    fetchInventory();
  }, []);

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

  const disabledAmounts = useMemo(() => {
    if (!inventory) return [];
    
    const isDispense = !isForeignToPhp(forex.serviceType);
    if (!isDispense) return [];

    // Check dispenser availability
    const denoms = config.acceptDenominations || []; // e.g. [10, 50] for USD
    const dispenser = inventory.bill_dispenser_counts || {};
    const available = denoms.filter(d => (dispenser[`${selectionCurrency}_${d}`] || 0) > 0);
    
    if (available.length === 0) {
      return config.amountOptions || [];
    }

    const minAvailable = Math.min(...available);
    return (config.amountOptions || []).filter(amount => amount % minAvailable !== 0);
  }, [inventory, config, forex.serviceType, selectionCurrency]);

  const warningMessage = useMemo(() => {
    if (!inventory) return null;
    const isDispense = !isForeignToPhp(forex.serviceType);
    if (!isDispense) return null;

    const denoms = config.acceptDenominations || [];
    const dispenser = inventory.bill_dispenser_counts || {};
    const available = denoms.filter(d => (dispenser[`${selectionCurrency}_${d}`] || 0) > 0);

    if (available.length === 0) {
      return `Warning: No ${selectionCurrency} bills are currently available in the dispenser.`;
    }

    const minAvailable = Math.min(...available);
    if (available.length < denoms.length) {
      const emptyDenoms = denoms.filter(d => !available.includes(d));
      const formattedEmpty = emptyDenoms.map(d => `${CURRENCY_SYMBOLS[selectionCurrency] || ""}${d}`).join(", ");
      return `Notice: ${formattedEmpty} bills are currently out of stock. Selected amount must be a multiple of ${CURRENCY_SYMBOLS[selectionCurrency] || ""}${minAvailable}.`;
    }

    return null;
  }, [inventory, config, forex.serviceType, selectionCurrency]);

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
            *This rate changes every 60 seconds
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
            targetCurrency="PHP"
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
            onSelect={setSelectedAmount}
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
            disabled={!forex.selectedAmount}
            className="min-w-[200px] !bg-coinnect-forex hover:!bg-coinnect-forex/90 !text-white"
          >
            Proceed
          </Button>
        </motion.div>
      </div>
    </PageLayout>
  );
}
