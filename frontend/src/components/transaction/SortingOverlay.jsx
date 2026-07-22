import { motion, AnimatePresence } from "framer-motion";

/**
 * Modal overlay displayed while a bill is being accepted, authenticated, or sorted into storage.
 * Pauses interaction and timer while active.
 */
export default function SortingOverlay({ isOpen, stepMessage }) {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          className="bg-white rounded-3xl p-8 md:p-10 max-w-md w-full shadow-2xl border border-gray-100 flex flex-col items-center text-center"
        >
          {/* Animated Spinner & Icon */}
          <div className="relative w-24 h-24 mb-6 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border-4 border-coinnect-primary/20 border-t-coinnect-primary animate-spin" />
            <motion.div
              animate={{ y: [-4, 4, -4] }}
              transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
              className="text-coinnect-primary font-bold text-3xl"
            >
              💵
            </motion.div>
          </div>

          {/* Heading */}
          <h3 className="text-2xl md:text-3xl font-bold text-gray-900 mb-3">
            Processing, Please Wait
          </h3>

          {/* Message */}
          <p className="text-gray-600 text-sm md:text-base leading-relaxed font-medium">
            {stepMessage || "Validating and sorting your bill. Please do not insert another bill."}
          </p>

          {/* Pulse Indicator */}
          <div className="mt-6 flex items-center gap-2 text-coinnect-primary font-semibold text-sm bg-coinnect-primary/10 px-4 py-2 rounded-full">
            <span className="w-2 h-2 rounded-full bg-coinnect-primary animate-ping" />
            <span>Sorting in Progress...</span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
