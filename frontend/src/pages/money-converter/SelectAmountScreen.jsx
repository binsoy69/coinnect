import { useNavigate, useParams } from "react-router-dom";
import { useMemo } from "react";
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
  const { transaction, setSelectedAmount, getServiceConfig } = useTransaction();

  const config = getServiceConfig() || SERVICE_CONFIG[type];

  const handleSelectAmount = (amount) => {
    setSelectedAmount(amount);
  };

  const handleProceed = () => {
    if (transaction.selectedAmount) {
      // For Coin-to-Bill, skip dispense selection and fee screens
      if (type === SERVICE_TYPES.COIN_TO_BILL) {
        navigate(getServiceRoute(ROUTES.CONFIRMATION, type));
      } else {
        navigate(getServiceRoute(ROUTES.SELECT_DISPENSE, type));
      }
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
            denominations={config?.amountOptions || []}
            selectedValue={transaction.selectedAmount}
            onSelect={handleSelectAmount}
            columns={3}
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
            disabled={!transaction.selectedAmount}
            className="px-20 py-6 text-2xl rounded-2xl"
          >
            Proceed
          </Button>
        </motion.div>
      </div>
    </PageLayout>
  );
}
