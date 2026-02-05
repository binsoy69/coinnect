import { useNavigate, useParams } from "react-router-dom";
import { useMemo } from "react";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import TransactionCard from "../../components/transaction/TransactionCard";
import { ROUTES, getServiceRoute } from "../../constants/routes";
import {
  SERVICE_CONFIG,
  TRANSACTION_TYPE_LABEL,
} from "../../constants/mockData";
import { useTransaction } from "../../context/TransactionContext";

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

export default function TransactionSummaryScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { transaction, getServiceConfig, getMoneyToDispense } =
    useTransaction();

  const config = getServiceConfig() || SERVICE_CONFIG[type];

  const handleBack = () => {
    navigate(getServiceRoute(ROUTES.INSERT_MONEY, type));
  };

  const handleProceed = () => {
    navigate(getServiceRoute(ROUTES.PROCESSING, type));
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
        subtitle: TRANSACTION_TYPE_LABEL,
        rightContent: serviceIndicator,
      }}
    >
      <div className="flex items-center justify-center min-h-[calc(100vh-140px)] py-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full max-w-lg"
        >
          <TransactionCard
            serviceType={type}
            serviceName={config?.name || ""}
            moneyInserted={transaction.moneyInserted}
            totalDue={transaction.totalDue}
            moneyToDispense={getMoneyToDispense()}
            selectedDenominations={transaction.selectedDispenseDenominations}
            showActions={true}
            onBack={handleBack}
            onProceed={handleProceed}
          />
        </motion.div>
      </div>
    </PageLayout>
  );
}
