import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import ServiceCard from "../../components/transaction/ServiceCard";
import { ROUTES } from "../../constants/routes";
import {
  CONVERTER_SERVICES,
  TRANSACTION_TYPE_LABEL,
} from "../../constants/mockData";
import { useTransaction } from "../../context/TransactionContext";

export default function ServiceSelectionScreen() {
  const navigate = useNavigate();
  const { startTransaction } = useTransaction();

  const handleSelectService = (serviceType) => {
    startTransaction(serviceType);
    navigate(ROUTES.REMINDER);
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: () => navigate(ROUTES.SELECT_TRANSACTION),
        subtitle: TRANSACTION_TYPE_LABEL,
      }}
    >
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)] py-4">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <h1 className="text-3xl font-bold text-gray-900">
            Select Type of Service
          </h1>
        </motion.div>

        {/* Service cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full max-w-5xl">
          {CONVERTER_SERVICES.map((service, index) => (
            <motion.div
              key={service.type}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <ServiceCard
                icon={service.icon}
                title={service.name}
                color="bg-coinnect-primary"
                onClick={() => handleSelectService(service.type)}
                className="h-full min-h-[200px]"
              />
            </motion.div>
          ))}
        </div>
      </div>
    </PageLayout>
  );
}
