import { useNavigate, useParams } from "react-router-dom";
import { useMemo, useState, useEffect } from "react";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import DenominationGrid from "../../components/transaction/DenominationGrid";
import Button from "../../components/common/Button";
import { ROUTES, SERVICE_TYPES, getServiceRoute } from "../../constants/routes";
import {
  SERVICE_CONFIG,
  TRANSACTION_TYPE_LABEL,
} from "../../constants/mockData";
import { useTransaction } from "../../context/TransactionContext";
import { useBackendTransaction } from "../../hooks/useBackendTransaction";

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

export default function SelectAmountScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { transaction, setSelectedAmount, getServiceConfig, setCurrentQuote } = useTransaction();
  const { fetchOptions, createQuote } = useBackendTransaction();

  const [optionsData, setOptionsData] = useState(null);
  const [isGeneratingQuote, setIsGeneratingQuote] = useState(false);
  const [quoteError, setQuoteError] = useState(null);

  const config = getServiceConfig() || SERVICE_CONFIG[type];

  useEffect(() => {
    let active = true;
    if (type) {
      fetchOptions(type).then((data) => {
        if (active && data) {
          setOptionsData(data);
        }
      });
    }
    return () => {
      active = false;
    };
  }, [type, fetchOptions]);

  const { denominations, disabledValues, reasonsMap } = useMemo(() => {
    if (optionsData?.options && optionsData.options.length > 0) {
      const denoms = optionsData.options.map((o) => o.amount);
      const disabled = optionsData.options
        .filter((o) => !o.enabled)
        .map((o) => o.amount);
      const reasons = Object.fromEntries(
        optionsData.options
          .filter((o) => !o.enabled)
          .map((o) => [o.amount, o.reason || "Temporarily unavailable"])
      );
      return { denominations: denoms, disabledValues: disabled, reasonsMap: reasons };
    }
    return {
      denominations: config?.amountOptions || [],
      disabledValues: config?.amountOptions || [],
      reasonsMap: Object.fromEntries((config?.amountOptions || []).map(amount => [amount, "Checking availability..."])),
    };
  }, [optionsData, config?.amountOptions]);

  const handleSelectAmount = (amount) => {
    setSelectedAmount(amount);
  };

  const handleProceed = async () => {
    if (!transaction.selectedAmount) return;

    // For Coin-to-Bill, generate quote now and proceed directly to confirmation
    if (type === SERVICE_TYPES.COIN_TO_BILL) {
      setIsGeneratingQuote(true);
      setQuoteError(null);
      try {
        const quote = await createQuote(type, transaction.selectedAmount, null);
        setCurrentQuote(quote);
        navigate(getServiceRoute(ROUTES.CONFIRMATION, type));
      } catch (err) {
        setQuoteError(err.message || "Failed to generate payout proposal. Please try again.");
      } finally {
        setIsGeneratingQuote(false);
      }
    } else {
      navigate(getServiceRoute(ROUTES.SELECT_DISPENSE, type));
    }
  };

  const handleBack = () => {
    navigate(ROUTES.MONEY_CONVERTER);
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
        showBack: true,
        onBack: handleBack,
        title: "Coin and Bill Converter",
        subtitle: config?.name || TRANSACTION_TYPE_LABEL,
        rightContent: serviceIndicator,
        className: "!py-2",
      }}
    >
      <div className="flex flex-col items-center py-2 h-[calc(100vh-100px)] justify-center">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <h1 className="text-4xl font-bold text-coinnect-primary">
            Select Your Transaction
          </h1>
        </motion.div>

        {/* Denomination grid */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="w-full max-w-4xl mb-12 flex justify-center"
        >
          <DenominationGrid
            denominations={denominations}
            disabledValues={disabledValues}
            reasonsMap={reasonsMap}
            selectedValue={transaction.selectedAmount}
            onSelect={handleSelectAmount}
            className="w-full justify-items-center gap-8"
          />
        </motion.div>

        {/* Proceed button */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-8"
        >
          <Button
            variant="primary"
            size="xl"
            onClick={handleProceed}
            disabled={!transaction.selectedAmount || isGeneratingQuote}
            className="px-20 py-6 text-2xl rounded-2xl"
          >
            {isGeneratingQuote ? "Checking..." : "Proceed"}
          </Button>
        </motion.div>
      </div>

      {quoteError && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center p-4 z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl text-center"
          >
            <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4 text-amber-600 text-2xl font-bold">
              !
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">
              Unavailable Selection
            </h3>
            <p className="text-gray-600 mb-6 text-sm">
              {quoteError}
            </p>
            <Button
              variant="primary"
              size="lg"
              onClick={() => setQuoteError(null)}
              className="w-full"
            >
              Choose Another Amount
            </Button>
          </motion.div>
        </div>
      )}
    </PageLayout>
  );
}
