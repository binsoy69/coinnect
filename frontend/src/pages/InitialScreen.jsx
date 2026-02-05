import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import Button from "../components/common/Button";
import Clock from "../components/common/Clock";
import SponsorPanel from "../components/layout/SponsorPanel";
import PageTransition from "../components/layout/PageTransition";
import { ROUTES } from "../constants/routes";

export default function InitialScreen() {
  const navigate = useNavigate();

  const handleStartTransaction = () => {
    navigate(ROUTES.SELECT_TRANSACTION);
  };

  return (
    <PageTransition>
      <div className="min-h-screen bg-gradient-to-br from-coinnect-navy to-coinnect-navy-dark">
        <div className="flex min-h-screen">
          {/* Main content - Left side (70%) */}
          <div className="flex-1 flex flex-col p-8 relative">
            {/* Top: Header Text */}
            <div className="z-10 mt-2 ml-4">
              <h1 className="text-white text-5xl font-bold mb-1 tracking-tight">
                Coinnect
              </h1>
              <p className="text-white/80 text-xl font-light">
                Simplifying your financial transaction!
              </p>
            </div>

            {/* Center: Main content */}
            <div className="flex-1 flex flex-col items-center justify-center -mt-10">
              {/* Animated Logo */}
              <motion.div
                animate={{ rotate: 360 }}
                transition={{
                  duration: 20,
                  repeat: Infinity,
                  ease: "linear",
                }}
                className="mb-8"
              >
                <img
                  src="/assets/Coinnect White.png"
                  alt="Coinnect"
                  className="h-48 w-48 object-contain"
                />
              </motion.div>

              {/* Start Button */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 }}
              >
                <Button
                  className="!bg-white !text-coinnect-navy-dark hover:bg-gray-100 px-12 py-4 rounded-full text-xl font-extrabold min-w-[300px] shadow-xl transition-transform hover:scale-105"
                  onClick={handleStartTransaction}
                >
                  Start Transaction
                </Button>
              </motion.div>
            </div>

            {/* Bottom: Clock */}
            <div className="absolute bottom-8 left-8">
              <Clock variant="light" showDate={true} className="text-left" />
            </div>
          </div>

          {/* Sponsor panel - Right side (30%) */}
          <div className="hidden lg:flex w-80 p-8 items-center">
            <SponsorPanel className="w-full" />
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
