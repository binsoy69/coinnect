import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import Button from '../../components/common/Button';
import WarningIcon from '../../components/feedback/WarningIcon';
import PageTransition from '../../components/layout/PageTransition';
import { ROUTES, getServiceRoute } from '../../constants/routes';

export default function WarningScreen() {
  const navigate = useNavigate();
  const { type } = useParams();

  const handleInsertMore = () => {
    navigate(getServiceRoute(ROUTES.INSERT_MONEY, type));
  };

  return (
    <PageTransition>
      <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center text-white max-w-2xl"
        >
          {/* Warning icon */}
          <div className="flex justify-center mb-8">
            <WarningIcon size={160} />
          </div>

          {/* Warning message */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-3xl font-bold mb-12 leading-relaxed"
          >
            The total amount you inserted does not match the selected transaction.
          </motion.h1>

          {/* Action button */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Button
              variant="white"
              size="xl"
              onClick={handleInsertMore}
              className="px-12"
            >
              Insert More Money
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </PageTransition>
  );
}
