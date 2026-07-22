import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import Button from '../../components/common/Button';
import PageTransition from '../../components/layout/PageTransition';
import { ROUTES, getServiceRoute } from '../../constants/routes';
import { useTransaction } from '../../context/TransactionContext';

import { formatPeso } from '../../constants/denominations';

// Question mark icon
const QuestionIcon = () => (
  <div className="w-32 h-32 mx-auto mb-8 rounded-full border-4 border-white flex items-center justify-center">
    <span className="text-6xl font-bold text-white">?</span>
  </div>
);

export default function TransactionFeeScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { transaction, setIncludeFee } = useTransaction();

  const feeAmount = transaction.fee || 10;

  const handleYes = () => {
    setIncludeFee(true);
    navigate(getServiceRoute(ROUTES.CONFIRMATION, type));
  };

  const handleNo = () => {
    setIncludeFee(false);
    navigate(getServiceRoute(ROUTES.CONFIRMATION, type));
  };

  return (
    <PageTransition>
      <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center text-white max-w-2xl"
        >
          {/* Question icon */}
          <QuestionIcon />

          {/* Question text */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-3xl font-bold mb-4"
          >
            Would you like to insert {formatPeso(feeAmount)} transaction fee?
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="text-white/80 text-sm mb-10 max-w-lg mx-auto"
          >
            Selecting <strong className="text-white">Yes</strong> adds {formatPeso(feeAmount)} to total cash to insert.<br/>
            Selecting <strong className="text-white">No</strong> deducts {formatPeso(feeAmount)} from your dispensed cash.
          </motion.p>

          {/* Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex gap-6 justify-center"
          >
            <Button
              variant="outline"
              size="xl"
              onClick={handleNo}
              className="px-16"
            >
              No
            </Button>
            <Button
              variant="white"
              size="xl"
              onClick={handleYes}
              className="px-16"
            >
              Yes
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </PageTransition>
  );
}
