import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRightLeft } from 'lucide-react';
import PageLayout from '../../components/layout/PageLayout';
import ServiceCard from '../../components/transaction/ServiceCard';
import { ROUTES } from '../../constants/routes';
import { FOREX_SERVICES } from '../../constants/forexData';
import { useForex } from '../../context/ForexContext';

export default function ForexServiceSelectionScreen() {
  const navigate = useNavigate();
  const { startForexTransaction } = useForex();

  const handleSelectService = (serviceType) => {
    startForexTransaction(serviceType);
    navigate(ROUTES.FOREX_REMINDER);
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: () => navigate(ROUTES.SELECT_TRANSACTION),
        subtitle: 'Foreign Exchange',
      }}
    >
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)] py-4">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <p className="text-coinnect-forex text-xl mb-2">Foreign Exchange</p>
          <h1 className="text-3xl font-bold text-gray-900">
            Select Type of Service
          </h1>
        </motion.div>

        {/* Service cards - 4 columns for forex */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-5xl">
          {FOREX_SERVICES.map((service, index) => (
            <motion.div
              key={service.type}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <ServiceCard
                icon={<ArrowRightLeft className="w-12 h-12" />}
                title={service.title}
                color="bg-coinnect-forex"
                onClick={() => handleSelectService(service.type)}
                className="h-full min-h-[180px]"
              />
            </motion.div>
          ))}
        </div>
      </div>
    </PageLayout>
  );
}
