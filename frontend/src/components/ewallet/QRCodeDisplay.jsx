import { motion } from "framer-motion";

export default function QRCodeDisplay({
  providerName = "GCash",
  onVerify,
  className = "",
  colorVariant = "gcash", // 'gcash' or 'maya'
}) {
  const textColor =
    colorVariant === "maya" ? "text-coinnect-maya" : "text-coinnect-gcash";
  const borderColor =
    colorVariant === "maya" ? "border-coinnect-maya" : "border-coinnect-gcash";
  const hoverBg =
    colorVariant === "maya"
      ? "hover:bg-coinnect-maya"
      : "hover:bg-coinnect-gcash";
  const instapayColor = colorVariant === "maya" ? "#01B463" : "#007DFE";
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex flex-col items-center text-center ${className}`}
    >
      {/* Heading */}
      <h2 className="text-2xl font-bold text-gray-900 mb-2">
        Scan QR Code ({providerName} App)
      </h2>
      <p className="text-gray-500 mb-6">
        Scan QR Code and input money you want to send.
      </p>

      {/* QR Code placeholder */}
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="w-56 h-56 bg-white border-2 border-gray-300 rounded-xl p-4 mb-6 flex items-center justify-center"
      >
        {/* Simple QR-like pattern */}
        <svg viewBox="0 0 100 100" className="w-full h-full">
          {/* Corner squares */}
          <rect x="5" y="5" width="25" height="25" fill="#333" rx="2" />
          <rect x="8" y="8" width="19" height="19" fill="white" rx="1" />
          <rect x="11" y="11" width="13" height="13" fill="#333" rx="1" />

          <rect x="70" y="5" width="25" height="25" fill="#333" rx="2" />
          <rect x="73" y="8" width="19" height="19" fill="white" rx="1" />
          <rect x="76" y="11" width="13" height="13" fill="#333" rx="1" />

          <rect x="5" y="70" width="25" height="25" fill="#333" rx="2" />
          <rect x="8" y="73" width="19" height="19" fill="white" rx="1" />
          <rect x="11" y="76" width="13" height="13" fill="#333" rx="1" />

          {/* Data pattern */}
          <rect x="35" y="5" width="5" height="5" fill="#333" />
          <rect x="45" y="5" width="5" height="5" fill="#333" />
          <rect x="55" y="5" width="5" height="5" fill="#333" />
          <rect x="35" y="15" width="5" height="5" fill="#333" />
          <rect x="50" y="15" width="5" height="5" fill="#333" />
          <rect x="60" y="15" width="5" height="5" fill="#333" />
          <rect x="40" y="25" width="5" height="5" fill="#333" />
          <rect x="55" y="25" width="5" height="5" fill="#333" />

          <rect x="5" y="35" width="5" height="5" fill="#333" />
          <rect x="15" y="35" width="5" height="5" fill="#333" />
          <rect x="25" y="35" width="5" height="5" fill="#333" />
          <rect x="35" y="35" width="5" height="5" fill="#333" />
          <rect x="45" y="35" width="5" height="5" fill="#333" />
          <rect x="55" y="35" width="5" height="5" fill="#333" />
          <rect x="65" y="35" width="5" height="5" fill="#333" />
          <rect x="80" y="35" width="5" height="5" fill="#333" />
          <rect x="90" y="35" width="5" height="5" fill="#333" />

          <rect x="10" y="45" width="5" height="5" fill="#333" />
          <rect x="25" y="45" width="5" height="5" fill="#333" />
          <rect x="40" y="45" width="5" height="5" fill="#333" />
          <rect x="50" y="45" width="5" height="5" fill="#333" />
          <rect x="65" y="45" width="5" height="5" fill="#333" />
          <rect x="75" y="45" width="5" height="5" fill="#333" />
          <rect x="85" y="45" width="5" height="5" fill="#333" />

          <rect x="5" y="55" width="5" height="5" fill="#333" />
          <rect x="20" y="55" width="5" height="5" fill="#333" />
          <rect x="35" y="55" width="5" height="5" fill="#333" />
          <rect x="45" y="55" width="5" height="5" fill="#333" />
          <rect x="60" y="55" width="5" height="5" fill="#333" />
          <rect x="75" y="55" width="5" height="5" fill="#333" />
          <rect x="90" y="55" width="5" height="5" fill="#333" />

          <rect x="5" y="65" width="5" height="5" fill="#333" />
          <rect x="15" y="65" width="5" height="5" fill="#333" />
          <rect x="30" y="65" width="5" height="5" fill="#333" />
          <rect x="45" y="65" width="5" height="5" fill="#333" />
          <rect x="55" y="65" width="5" height="5" fill="#333" />
          <rect x="70" y="65" width="5" height="5" fill="#333" />
          <rect x="85" y="65" width="5" height="5" fill="#333" />

          <rect x="35" y="75" width="5" height="5" fill="#333" />
          <rect x="50" y="75" width="5" height="5" fill="#333" />
          <rect x="65" y="75" width="5" height="5" fill="#333" />
          <rect x="80" y="75" width="5" height="5" fill="#333" />
          <rect x="90" y="75" width="5" height="5" fill="#333" />

          <rect x="40" y="85" width="5" height="5" fill="#333" />
          <rect x="55" y="85" width="5" height="5" fill="#333" />
          <rect x="70" y="85" width="5" height="5" fill="#333" />
          <rect x="85" y="85" width="5" height="5" fill="#333" />

          <rect x="35" y="90" width="5" height="5" fill="#333" />
          <rect x="50" y="90" width="5" height="5" fill="#333" />
          <rect x="60" y="90" width="5" height="5" fill="#333" />
          <rect x="75" y="90" width="5" height="5" fill="#333" />
          <rect x="90" y="90" width="5" height="5" fill="#333" />

          {/* Center text */}
          <text
            x="50"
            y="52"
            textAnchor="middle"
            fill={instapayColor}
            fontSize="7"
            fontWeight="bold"
          >
            instaPay
          </text>
        </svg>
      </motion.div>

      {/* After paying text */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        className={`${textColor} italic mb-6`}
      >
        After paying, click the button
      </motion.p>

      {/* Verify button */}
      <motion.button
        type="button"
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={onVerify}
        className={`px-10 py-3 rounded-button text-lg font-semibold border-2 ${borderColor} ${textColor} ${hoverBg} hover:text-white transition-colors`}
      >
        Verify Transaction
      </motion.button>
    </motion.div>
  );
}
