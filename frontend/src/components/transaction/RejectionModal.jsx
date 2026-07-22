import { motion, AnimatePresence } from "framer-motion";
import Button from "../common/Button";
import WarningIcon from "../feedback/WarningIcon";

const REJECTION_MESSAGES = {
  STORAGE_FULL: {
    title: "Storage Cassette Full",
    message: "The storage slot for this bill is full. Please insert a different denomination.",
    isCritical: false,
  },
  AUTHENTICATION_FAILED: {
    title: "Bill Unauthenticated",
    message: "The bill could not be verified. Please check the condition of the bill and try again.",
    isCritical: false,
  },
  UNEXPECTED_DENOMINATION: {
    title: "Unrecognized Bill",
    message: "The inserted bill denomination or currency is not accepted for this transaction.",
    isCritical: false,
  },
  POSITIONING_FAILED: {
    title: "Intake Error",
    message: "The bill was not pulled in properly. Please flatten the bill and re-insert.",
    isCritical: false,
  },
  JAM: {
    title: "Hardware Jam Detected",
    message: "A hardware jam occurred in the bill acceptor. Please notify an operator for assistance.",
    isCritical: true,
  },
  HARDWARE_FAULT: {
    title: "Hardware Fault",
    message: "A hardware component error was detected. Please seek staff assistance.",
    isCritical: true,
  },
  TIMEOUT: {
    title: "Acceptance Timeout",
    message: "No bill was detected within the time limit. Please insert your bill clearly.",
    isCritical: false,
  },
};

/**
 * Modal popup displayed when a bill is rejected or a hardware error occurs.
 */
export default function RejectionModal({
  isOpen,
  error,
  onClose,
  onNavigateWarning,
  onChangeSelection,
}) {
  if (!isOpen || !error) return null;

  // Resolve reason code from error string or dict
  const reasonCode = typeof error === "string" 
    ? (error.includes("STORAGE_FULL") ? "STORAGE_FULL"
      : error.includes("AUTHENTICATION_FAILED") ? "AUTHENTICATION_FAILED"
      : error.includes("POSITIONING") ? "POSITIONING_FAILED"
      : error.includes("JAM") ? "JAM"
      : error.includes("HARDWARE") ? "HARDWARE_FAULT"
      : "UNEXPECTED_DENOMINATION")
    : (error.reason || error.error_code || "UNEXPECTED_DENOMINATION");

  const config = REJECTION_MESSAGES[reasonCode] || {
    title: "Bill Rejected",
    message: typeof error === "string" ? error : (error.message || error.reason || "The bill was rejected. Please try again."),
    isCritical: false,
  };

  const handleConfirm = () => {
    if (config.isCritical && onNavigateWarning) {
      onNavigateWarning();
    } else {
      onClose();
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="bg-white rounded-3xl p-6 md:p-8 max-w-md w-full shadow-2xl border border-gray-100 flex flex-col items-center text-center"
        >
          {/* Warning Icon */}
          <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mb-4 text-red-600">
            <WarningIcon className="w-10 h-10" />
          </div>

          {/* Title */}
          <h3 className="text-2xl font-bold text-gray-900 mb-2">
            {config.title}
          </h3>

          {/* Message */}
          <p className="text-gray-600 text-sm md:text-base mb-6 leading-relaxed">
            {config.message}
          </p>

          {/* Action Buttons */}
          <div className="w-full flex flex-col gap-3">
            <Button
              variant="primary"
              size="lg"
              onClick={handleConfirm}
              className="w-full font-bold shadow-lg"
            >
              {config.isCritical ? "Go to Warning / Help" : "OK, Try Again"}
            </Button>
            {!config.isCritical && onChangeSelection && (
              <Button
                variant="outline"
                size="lg"
                onClick={onChangeSelection}
                className="w-full font-semibold border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                Choose Different Bill
              </Button>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
