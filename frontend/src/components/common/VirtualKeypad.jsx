import { motion } from "framer-motion";
import { Delete } from "lucide-react";

export default function VirtualKeypad({
  value = "",
  onChange,
  onSubmit,
  maxLength = 11,
  placeholder = "",
  submitLabel = "Proceed",
  className = "",
  colorClass = "coinnect-ewallet", // 'coinnect-gcash' or 'coinnect-maya'
}) {
  const borderColor = `border-${colorClass}`;
  const textColor = `text-${colorClass}`;
  const bgColor = `bg-${colorClass}`;
  const handleKeyPress = (key) => {
    if (key === "backspace") {
      onChange(value.slice(0, -1));
    } else if (value.length < maxLength) {
      onChange(value + key);
    }
  };

  const keys = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["", "0", "backspace"],
  ];

  return (
    <div className={`flex flex-col items-center ${className}`}>
      {/* Display field */}
      <div className="w-full max-w-lg mb-4 lg:mb-8">
        <div
          className={`border-2 ${borderColor} rounded-xl p-3 lg:p-4 min-h-[50px] lg:min-h-[70px] flex items-center justify-center`}
        >
          {value ? (
            <span
              className={`text-2xl lg:text-3xl font-bold ${textColor} tracking-[0.3em] text-center`}
            >
              {value}
            </span>
          ) : (
            <span className="text-2xl lg:text-3xl font-bold text-gray-300 tracking-[0.3em] text-center">
              {placeholder}
            </span>
          )}
        </div>
      </div>

      {/* Keypad grid */}
      <div className="grid grid-cols-3 gap-2 lg:gap-4 max-w-md w-full mb-4 lg:mb-8">
        {keys.flat().map((key, index) => {
          if (key === "") {
            return <div key={index} />;
          }

          if (key === "backspace") {
            return (
              <motion.button
                key="backspace"
                type="button"
                whileTap={{ scale: 0.9 }}
                onClick={() => handleKeyPress("backspace")}
                className={`flex items-center justify-center p-3 lg:p-4 rounded-xl ${textColor} hover:bg-gray-100 transition-colors min-h-[48px] lg:min-h-[60px]`}
              >
                <Delete className="w-6 h-6 lg:w-8 lg:h-8" />
              </motion.button>
            );
          }

          return (
            <motion.button
              key={key}
              type="button"
              whileTap={{ scale: 0.9 }}
              onClick={() => handleKeyPress(key)}
              className={`flex items-center justify-center p-3 lg:p-4 rounded-xl text-2xl lg:text-3xl font-bold ${textColor} hover:bg-gray-100 transition-colors min-h-[48px] lg:min-h-[60px]`}
            >
              {key}
            </motion.button>
          );
        })}
      </div>

      {/* Submit button */}
      <motion.button
        type="button"
        whileHover={value.length > 0 ? { scale: 1.02 } : {}}
        whileTap={value.length > 0 ? { scale: 0.98 } : {}}
        onClick={() => value.length > 0 && onSubmit?.(value)}
        disabled={value.length === 0}
        className={`
          px-12 py-3 rounded-button text-xl font-semibold border-2 ${borderColor} transition-colors
          ${
            value.length > 0
              ? `${textColor} hover:${bgColor} hover:text-white cursor-pointer`
              : "text-gray-300 border-gray-300 cursor-not-allowed"
          }
        `}
      >
        {submitLabel}
      </motion.button>
    </div>
  );
}
