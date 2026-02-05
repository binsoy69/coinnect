import { useNavigate, useParams } from 'react-router-dom';
import { useMemo } from 'react';
import { motion } from 'framer-motion';
import PageLayout from '../../components/layout/PageLayout';
import Card from '../../components/common/Card';
import DenominationCheckbox from '../../components/transaction/DenominationCheckbox';
import Button from '../../components/common/Button';
import Clock from '../../components/common/Clock';
import { ROUTES, getServiceRoute } from '../../constants/routes';
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
  const { transaction, toggleDispenseDenomination, getServiceConfig } = useTransaction();

  const config = getServiceConfig() || SERVICE_CONFIG[type];

  const handleProceed = () => {
    if (transaction.selectedDispenseDenominations.length > 0) {
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
      <div className="py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left panel - Summary */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <Card variant="orange" animated={false} className="p-8 h-full">
              <div className="space-y-6">
                {/* Money Inserted */}
                <div>
                  <p className="text-white/70 text-sm mb-1">Money Inserted</p>
                  <p className="text-4xl font-bold">
                    {formatPeso(transaction.selectedAmount || 0)}
                  </p>
                </div>

                {/* Transaction Fee */}
                <div>
                  <p className="text-white/70 text-sm mb-1">Transaction Fee</p>
                  <p className="text-2xl font-bold">
                    {formatPeso(config?.fee || 0)}
                  </p>
                </div>

                {/* DateTime */}
                <div className="pt-4 border-t border-white/20">
                  <Clock variant="light" />
                </div>
              </div>
            </Card>
          </motion.div>

          {/* Right panel - Denomination selection */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex flex-col"
          >
            <h2 className="text-2xl font-bold text-gray-900 mb-6">
              Select Denomination to Dispense
            </h2>

            <DenominationCheckbox
              denominations={config?.dispenseOptions || []}
              selectedValues={transaction.selectedDispenseDenominations}
              onToggle={toggleDispenseDenomination}
              columns={2}
              className="mb-8"
            />

            <Button
              variant="primary"
              size="xl"
              onClick={handleProceed}
              disabled={transaction.selectedDispenseDenominations.length === 0}
              className="mt-auto"
              fullWidth
            >
              Proceed
            </Button>
          </motion.div>
        </div>
      </div>
    </PageLayout>
  );
}
