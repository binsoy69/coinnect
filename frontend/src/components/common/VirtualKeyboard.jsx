import { motion } from "framer-motion";
import { Delete } from "lucide-react";

export default function VirtualKeyboard({
  value = "",
  onChange,
  onSubmit,
  maxLength = 120,
  placeholder = "",
  submitLabel = "Proceed",
  className = "",
  colorClass = "coinnect-ewallet", // 'coinnect-gcash' or 'coinnect-maya'
}) {
  // Safe classes mapping to avoid Tailwind dynamic compilation issues
  const borderClasses = {
    "coinnect-gcash": "border-coinnect-gcash",
    "coinnect-maya": "border-coinnect-maya",
    "coinnect-ewallet": "border-coinnect-ewallet",
  };
  const textClasses = {
    "coinnect-gcash": "text-coinnect-gcash",
    "coinnect-maya": "text-coinnect-maya",
    "coinnect-ewallet": "text-coinnect-ewallet",
  };
  const hoverBgClasses = {
    "coinnect-gcash": "hover:bg-coinnect-gcash/10",
    "coinnect-maya": "hover:bg-coinnect-maya/10",
    "coinnect-ewallet": "hover:bg-coinnect-ewallet/10",
  };
  const activeBgClasses = {
    "coinnect-gcash": "hover:bg-coinnect-gcash hover:text-white",
    "coinnect-maya": "hover:bg-coinnect-maya hover:text-white",
    "coinnect-ewallet": "hover:bg-coinnect-ewallet hover:text-white",
  };

  const borderColor = borderClasses[colorClass] || "border-coinnect-ewallet";
  const textColor = textClasses[colorClass] || "text-coinnect-ewallet";
  const hoverBgColor = hoverBgClasses[colorClass] || "hover:bg-coinnect-ewallet/10";
  const activeBgColor = activeBgClasses[colorClass] || "hover:bg-coinnect-ewallet hover:text-white";

  const handleKeyPress = (key) => {
    if (key === "BACKSPACE") {
      onChange(value.slice(0, -1));
    } else if (key === "CLEAR") {
      onChange("");
    } else if (key === "SPACE") {
      if (value.length < maxLength) {
        onChange(value + " ");
      }
    } else {
      if (value.length < maxLength) {
        onChange(value + key);
      }
    }
  };

  const rows = [
    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
    ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
    ["Z", "X", "C", "V", "B", "N", "M"],
  ];

  const isSubmitDisabled = value.trim().length < 2;

  return (
    <div className={`flex flex-col items-center gap-3 lg:gap-4 w-full ${className}`}>
      {/* Display field */}
      <div className="w-full max-w-2xl mb-2">
        <div
          className={`border-2 ${borderColor} rounded-xl p-3 lg:p-4 min-h-[50px] lg:min-h-[70px] flex items-center justify-center bg-white`}
        >
          {value ? (
            <span
              className={`text-xl lg:text-2xl font-bold ${textColor} tracking-wide text-center`}
            >
              {value}
            </span>
          ) : (
            <span className="text-xl lg:text-2xl font-bold text-gray-300 tracking-wide text-center">
              {placeholder}
            </span>
          )}
        </div>
      </div>

      {/* QWERTY rows */}
      <div className="flex flex-col gap-2 w-full max-w-2xl">
        {/* Row 1 */}
        <div className="grid grid-cols-10 gap-1.5 w-full">
          {rows[0].map((key) => (
            <motion.button
              key={key}
              type="button"
              whileTap={{ scale: 0.9 }}
              onClick={() => handleKeyPress(key)}
              className={`flex items-center justify-center p-2.5 lg:p-3.5 rounded-lg border border-gray-200 bg-white text-lg lg:text-xl font-bold ${textColor} ${hoverBgColor} active:scale-95 transition-all`}
            >
              {key}
            </motion.button>
          ))}
        </div>

        {/* Row 2 */}
        <div className="flex justify-center gap-1.5 w-full px-[4%]">
          {rows[1].map((key) => (
            <motion.button
              key={key}
              type="button"
              whileTap={{ scale: 0.9 }}
              onClick={() => handleKeyPress(key)}
              className={`flex-1 flex items-center justify-center p-2.5 lg:p-3.5 rounded-lg border border-gray-200 bg-white text-lg lg:text-xl font-bold ${textColor} ${hoverBgColor} active:scale-95 transition-all min-w-[32px]`}
            >
              {key}
            </motion.button>
          ))}
        </div>

        {/* Row 3 */}
        <div className="flex justify-center gap-1.5 w-full px-[12%]">
          {rows[2].map((key) => (
            <motion.button
              key={key}
              type="button"
              whileTap={{ scale: 0.9 }}
              onClick={() => handleKeyPress(key)}
              className={`flex-1 flex items-center justify-center p-2.5 lg:p-3.5 rounded-lg border border-gray-200 bg-white text-lg lg:text-xl font-bold ${textColor} ${hoverBgColor} active:scale-95 transition-all min-w-[32px]`}
            >
              {key}
            </motion.button>
          ))}
        </div>

        {/* Row 4 (Controls) */}
        <div className="flex justify-center gap-1.5 w-full">
          <motion.button
            type="button"
            whileTap={{ scale: 0.95 }}
            onClick={() => handleKeyPress("CLEAR")}
            className={`flex-[2] flex items-center justify-center p-2.5 lg:p-3.5 rounded-lg border border-gray-200 bg-white text-sm lg:text-base font-bold ${textColor} ${hoverBgColor} transition-colors`}
          >
            CLEAR
          </motion.button>
          <motion.button
            type="button"
            whileTap={{ scale: 0.95 }}
            onClick={() => handleKeyPress("SPACE")}
            className={`flex-[6] flex items-center justify-center p-2.5 lg:p-3.5 rounded-lg border border-gray-200 bg-white text-sm lg:text-base font-bold ${textColor} ${hoverBgColor} transition-colors`}
          >
            SPACE
          </motion.button>
          <motion.button
            type="button"
            whileTap={{ scale: 0.95 }}
            onClick={() => handleKeyPress("BACKSPACE")}
            className={`flex-[2] flex items-center justify-center p-2.5 lg:p-3.5 rounded-lg border border-gray-200 bg-white font-bold ${textColor} ${hoverBgColor} transition-colors`}
          >
            <Delete className="w-5 h-5 lg:w-6 h-6 mx-auto" />
          </motion.button>
        </div>
      </div>

      {/* Submit Button */}
      <motion.button
        type="button"
        whileHover={!isSubmitDisabled ? { scale: 1.02 } : {}}
        whileTap={!isSubmitDisabled ? { scale: 0.98 } : {}}
        onClick={() => !isSubmitDisabled && onSubmit?.(value)}
        disabled={isSubmitDisabled}
        className={`
          px-12 py-3 rounded-button text-lg lg:text-xl font-semibold border-2 ${borderColor} transition-colors mt-2 lg:mt-4
          ${
            !isSubmitDisabled
              ? `${textColor} ${activeBgColor} cursor-pointer bg-white`
              : "text-gray-300 border-gray-300 cursor-not-allowed bg-gray-50"
          }
        `}
      >
        {submitLabel}
      </motion.button>
    </div>
  );
}
