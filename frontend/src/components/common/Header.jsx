import { useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { motion } from "framer-motion";
import Clock from "./Clock";

export default function Header({
  showBack = false,
  onBack,
  title = "",
  subtitle = "",
  showClock = true,
  rightContent = null,
  variant = "light", // 'light' for gray bg pages, 'dark' for orange bg pages
  className = "",
}) {
  const navigate = useNavigate();

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      navigate(-1);
    }
  };

  const textColor = variant === "dark" ? "text-white" : "text-gray-900";
  const subtitleColor = variant === "dark" ? "text-white/80" : "text-gray-600";

  return (
    <header className={`flex items-center justify-between py-4 ${className}`}>
      {/* Left side: Back button + Logo/Title */}
      <div className="flex items-center gap-4">
        {showBack && (
          <motion.button
            onClick={handleBack}
            whileTap={{ scale: 0.95 }}
            className={`p-2 rounded-full hover:bg-black/10 transition-colors ${textColor}`}
          >
            <ChevronLeft className="w-8 h-8" />
          </motion.button>
        )}

        <div className="flex items-center gap-4">
          <img
            src={
              variant === "dark"
                ? "/assets/Coinnect Logo White.png"
                : "/assets/Coinnect Logo.png"
            }
            alt="Coinnect"
            className="h-12 w-auto"
          />
          <div className="flex flex-col -gap-1">
            <span className={`text-2xl font-bold tracking-tight ${textColor}`}>
              Coinnect
            </span>
            <span className={`text-xs ${subtitleColor}`}>
              Simplifying your financial transaction!
            </span>
          </div>

          {(title || subtitle) && (
            <div
              className={`flex flex-col pl-4 ml-4 border-l ${variant === "dark" ? "border-white/20" : "border-gray-200"}`}
            >
              {subtitle && (
                <span className={`text-sm ${subtitleColor}`}>{subtitle}</span>
              )}
              {title && (
                <span className={`text-lg font-semibold ${textColor}`}>
                  {title}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right side: Clock and/or custom content */}
      <div className="flex items-center gap-6">
        {rightContent}
        {showClock && <Clock variant={variant === "dark" ? "light" : "dark"} />}
      </div>
    </header>
  );
}
