import { useNavigate, useParams } from "react-router-dom";
import { useEffect } from "react";
import { motion } from "framer-motion";
import LoadingDots from "../../components/common/LoadingDots";
import PageTransition from "../../components/layout/PageTransition";
import { ROUTES, getServiceRoute } from "../../constants/routes";

export default function ProcessingScreen() {
  const navigate = useNavigate();
  const { type } = useParams();

  // Auto-advance to success screen after 2 seconds (simulated processing)
  useEffect(() => {
    const timer = setTimeout(() => {
      navigate(getServiceRoute(ROUTES.SUCCESS, type));
    }, 2500);

    return () => clearTimeout(timer);
  }, [navigate, type]);

  return (
    <PageTransition>
      <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center text-white"
        >
          {/* Loading dots */}
          <LoadingDots count={5} color="white" className="mb-8" />

          {/* Status text */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-3xl font-bold mb-3"
          >
            Dispensing Money
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-lg text-white/80"
          >
            Please wait...
          </motion.p>
        </motion.div>
      </div>
    </PageTransition>
  );
}
