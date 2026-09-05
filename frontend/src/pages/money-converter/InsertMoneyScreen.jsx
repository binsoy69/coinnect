import { useNavigate, useParams } from "react-router-dom";
import { useState, useEffect, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import InsertMoneyPanel from "../../components/transaction/InsertMoneyPanel";
import MoneyCounter from "../../components/transaction/MoneyCounter";
import Button from "../../components/common/Button";
import { ROUTES, getServiceRoute } from "../../constants/routes";
import {
  SERVICE_CONFIG,
  TRANSACTION_TYPE_LABEL,
} from "../../constants/mockData";
import { useTransaction } from "../../context/TransactionContext";
import { useBackendTransaction } from "../../hooks/useBackendTransaction";
import { formatPeso } from "../../constants/denominations";
import { ENABLE_KEYBOARD_SIM } from "../../constants/api";
import RejectionModal from "../../components/transaction/RejectionModal";
import SortingOverlay from "../../components/transaction/SortingOverlay";
import PayoutReapprovalModal from "../../components/transaction/PayoutReapprovalModal";
import { useBillAcceptance } from "../../hooks/useBillAcceptance";

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
  const { transaction, setBackendState, getServiceConfig, isAmountMatched } =
    useTransaction();
  const {
    simulateInsert,
    transactionId,
    backendState,
    cancelBackendTransaction,
    approveQuote,
    requestClaim,
  } = useBackendTransaction();
  const [, setResetCounter] = useState(0);
  const [isApprovingQuote, setIsApprovingQuote] = useState(false);
  const hasAcceptedCash = transaction.moneyInserted > 0 || (backendState?.inserted_amount || 0) > 0;

  const config = getServiceConfig() || SERVICE_CONFIG[type];

  const isIntakeBlocked =
    Boolean(backendState?.pending_quote) ||
    backendState?.accounting_fault;

  // Physical bill acceptor loop - pause during reapproval or accounting fault
  const { isSorting, lastError, clearError } = useBillAcceptance(
    transactionId,
    "/transaction",
    !isAmountMatched() && (config?.insertType || "bill") === "bill" && !isIntakeBlocked,
    (snapshot) => setBackendState(snapshot)
  );

  // Auto-navigate to warning if claim required
  useEffect(() => {
    if (backendState?.state === "CLAIM_REQUIRED" || Boolean(backendState?.claim_ticket_code)) {
      navigate(getServiceRoute(ROUTES.WARNING, type));
    }
  }, [backendState?.state, backendState?.claim_ticket_code, navigate, type]);

  const handleApproveQuote = async (quoteId) => {
    setIsApprovingQuote(true);
    try {
      await approveQuote(quoteId);
    } catch (err) {
      console.error("Failed to approve quote:", err);
    } finally {
      setIsApprovingQuote(false);
    }
  };

  const handleRequestClaim = async () => {
    try {
      await requestClaim();
      navigate(getServiceRoute(ROUTES.WARNING, type));
    } catch (err) {
      console.error("Failed to request claim:", err);
    }
  };

  const handleClearError = useCallback(() => {
    clearError();
    setResetCounter((c) => c + 1);
  }, [clearError]);

  const handleChangeSelection = useCallback(async () => {
    clearError();
    if (hasAcceptedCash) return;
    if (transactionId) {
      try {
        await cancelBackendTransaction();
      } catch {
        return;
      }
    }
    navigate(getServiceRoute(ROUTES.SELECT_AMOUNT, type));
  }, [clearError, hasAcceptedCash, transactionId, cancelBackendTransaction, navigate, type]);

  // Auto-navigate when inserted amount meets or exceeds the required amount
  useEffect(() => {
    if (backendState?.can_confirm) {
      navigate(getServiceRoute(ROUTES.TRANSACTION_SUMMARY, type));
    }
  }, [backendState?.can_confirm, navigate, type]);

  // Keyboard simulation for development (toggleable via VITE_ENABLE_KEYBOARD_SIM)
  // Press keys 1-4 to insert different denominations
  useEffect(() => {
    if (!ENABLE_KEYBOARD_SIM) return;

    const handleKeyPress = (e) => {
      const keyMap = {
        1: config?.insertCounters[0],
        2: config?.insertCounters[1],
        3: config?.insertCounters[2],
        4: config?.insertCounters[3],
      };

      if (keyMap[e.key]) {
        const denom = keyMap[e.key];
        const insertType = config?.insertType || "bill";
        simulateInsert(denom, insertType);
      }
    };

    window.addEventListener("keypress", handleKeyPress);
    return () => window.removeEventListener("keypress", handleKeyPress);
  }, [simulateInsert, config?.insertCounters, config?.insertType]);

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
        showBack: !hasAcceptedCash,
        onBack: handleChangeSelection,
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
      <SortingOverlay isOpen={isSorting} />
      <RejectionModal
        isOpen={Boolean(lastError)}
        error={lastError}
        onClose={handleClearError}
        onNavigateWarning={() => navigate(getServiceRoute(ROUTES.WARNING, type))}
        onChangeSelection={handleChangeSelection}
      />
      <PayoutReapprovalModal
        pendingQuote={backendState?.pending_quote}
        onApprove={handleApproveQuote}
        onRequestClaim={handleRequestClaim}
        isLoading={isApprovingQuote}
      />

    </PageLayout>
  );
}
