import { useNavigate, useParams } from 'react-router-dom';
import { useMemo } from 'react';
import { motion } from 'framer-motion';
import PageLayout from '../../components/layout/PageLayout';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import Clock from '../../components/common/Clock';
import { ROUTES, getServiceRoute, SERVICE_TYPES } from '../../constants/routes';
import { SERVICE_CONFIG, TRANSACTION_TYPE_LABEL } from '../../constants/mockData';
import { useTransaction } from '../../context/TransactionContext';
import { formatPeso } from '../../constants/denominations';

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

export default function SelectDispenseScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { transaction, setDispenseCount, getServiceConfig } = useTransaction();

  const config = getServiceConfig() || SERVICE_CONFIG[type];
  const targetAmount = transaction.selectedAmount || 0;

  // Filter dispense options: for bill-to-bill, only allow denominations strictly smaller than target amount
  const availableDenominations = useMemo(() => {
    const opts = config?.dispenseOptions || [];
    if (type === SERVICE_TYPES.BILL_TO_BILL && targetAmount > 0) {
      return opts.filter((d) => d < targetAmount);
    }
    return opts;
  }, [config?.dispenseOptions, type, targetAmount]);

  const counts = transaction.selectedDispenseCounts || {};

  // Calculate total allocated money
  const allocatedTotal = useMemo(() => {
    return Object.entries(counts).reduce((sum, [denom, count]) => {
      return sum + (Number(denom) * (count || 0));
    }, 0);
  }, [counts]);

  const remainingToAllocate = targetAmount - allocatedTotal;

  const handleIncrement = (denom) => {
    if (allocatedTotal + denom <= targetAmount) {
      const current = counts[denom] || 0;
      setDispenseCount(denom, current + 1);
    }
  };

  const handleDecrement = (denom) => {
    const current = counts[denom] || 0;
    if (current > 0) {
      setDispenseCount(denom, current - 1);
    }
  };

  const handleProceed = () => {
    if (allocatedTotal > 0 || transaction.selectedDispenseDenominations.length > 0) {
      navigate(getServiceRoute(ROUTES.TRANSACTION_FEE, type));
    }
  };

  const handleBack = () => {
    navigate(getServiceRoute(ROUTES.SELECT_AMOUNT, type));
  };

  const serviceIndicator = useMemo(() => (
    <ServiceIndicator icon={config?.icon} shortName={config?.shortName} />
  ), [config?.icon, config?.shortName]);

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: handleBack,
        subtitle: TRANSACTION_TYPE_LABEL,
        rightContent: serviceIndicator,
      }}
    >
      <div className="py-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left panel - Summary */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="lg:col-span-5"
          >
            <Card variant="orange" animated={false} className="p-6 h-full flex flex-col justify-between">
              <div className="space-y-6">
                <div>
                  <p className="text-white/70 text-sm mb-1">Target Amount</p>
                  <p className="text-4xl font-bold">
                    {formatPeso(targetAmount)}
                  </p>
                </div>

                <div className="bg-white/10 p-4 rounded-2xl space-y-3">
                  <div className="flex justify-between items-center text-sm text-white/80">
                    <span>Allocated Breakdown:</span>
                    <span className="font-bold text-white text-lg">{formatPeso(allocatedTotal)}</span>
                  </div>
                  <div className="flex justify-between items-center text-sm text-white/80">
                    <span>Remaining Balance:</span>
                    <span className={`font-bold text-lg ${remainingToAllocate === 0 ? "text-green-300" : "text-amber-300"}`}>
                      {formatPeso(Math.max(0, remainingToAllocate))}
                    </span>
                  </div>
                  {remainingToAllocate > 0 && (
                    <p className="text-xs text-white/70 italic pt-1 border-t border-white/10">
                      Unallocated {formatPeso(remainingToAllocate)} will be auto-filled with largest available bills.
                    </p>
                  )}
                </div>

                <div>
                  <p className="text-white/70 text-sm mb-1">Transaction Fee</p>
                  <p className="text-2xl font-bold">
                    {formatPeso(transaction.fee || config?.fee || 0)}
                  </p>
                </div>
              </div>

              <div className="pt-4 border-t border-white/20 mt-6">
                <Clock variant="light" />
              </div>
            </Card>
          </motion.div>

          {/* Right panel - Quantity breakdown selection */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="lg:col-span-7 flex flex-col justify-between"
          >
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Select Dispense Breakdown
              </h2>
              <p className="text-gray-500 text-sm mb-6">
                Specify how many of each denomination you would like to receive.
              </p>

              {availableDenominations.length === 0 ? (
                <div className="bg-amber-50 border border-amber-200 text-amber-800 p-6 rounded-2xl text-center">
                  No lower denominations available for this amount.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                  {availableDenominations.map((denom) => {
                    const count = counts[denom] || 0;
                    const canAdd = allocatedTotal + denom <= targetAmount;
                    return (
                      <div
                        key={denom}
                        className={`p-4 rounded-2xl border-2 transition-all flex items-center justify-between ${
                          count > 0
                            ? 'border-coinnect-primary bg-coinnect-primary/5 shadow-sm'
                            : 'border-gray-200 bg-white'
                        }`}
                      >
                        <div>
                          <p className="text-xl font-bold text-gray-900">
                            {formatPeso(denom)}
                          </p>
                          <p className="text-xs text-gray-500">
                            Subtotal: {formatPeso(denom * count)}
                          </p>
                        </div>

                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={() => handleDecrement(denom)}
                            disabled={count <= 0}
                            className="w-10 h-10 rounded-full border border-gray-300 flex items-center justify-center text-xl font-bold text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-100 active:scale-95 transition-all"
                          >
                            -
                          </button>
                          <span className="w-8 text-center text-xl font-bold text-gray-900">
                            {count}
                          </span>
                          <button
                            type="button"
                            onClick={() => handleIncrement(denom)}
                            disabled={!canAdd}
                            className="w-10 h-10 rounded-full bg-coinnect-primary text-white flex items-center justify-center text-xl font-bold disabled:opacity-30 disabled:cursor-not-allowed hover:bg-coinnect-primary/90 active:scale-95 transition-all shadow-md"
                          >
                            +
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <Button
              variant="primary"
              size="xl"
              onClick={handleProceed}
              disabled={allocatedTotal === 0 && availableDenominations.length > 0 && targetAmount > 0}
              className="w-full py-5 rounded-2xl text-xl font-bold"
            >
              Proceed
            </Button>
          </motion.div>
        </div>
      </div>
    </PageLayout>
  );
}
