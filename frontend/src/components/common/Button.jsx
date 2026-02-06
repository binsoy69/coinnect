import { motion } from "framer-motion";

const variants = {
  primary:
    "bg-coinnect-primary text-white hover:bg-coinnect-primary-dark focus:ring-coinnect-primary",
  secondary:
    "bg-white/80 text-coinnect-primary border border-white hover:bg-white",
  outline: "bg-transparent border-2 border-white text-white hover:bg-white/10",
  ghost: "bg-transparent text-coinnect-primary hover:bg-coinnect-primary/10",
  "outline-orange":
    "bg-transparent border-2 border-coinnect-primary text-coinnect-primary hover:bg-coinnect-primary/10",
  white: "bg-white text-coinnect-primary hover:bg-gray-100",
  "white-blue": "bg-white text-coinnect-gcash hover:bg-gray-50",
  "white-green": "bg-white text-coinnect-maya hover:bg-gray-50",
  ewallet: "bg-coinnect-ewallet text-white hover:bg-coinnect-ewallet-dark",
  gcash: "bg-coinnect-gcash text-white hover:opacity-90",
  maya: "bg-coinnect-maya text-white hover:opacity-90",
};

const sizes = {
  sm: "px-4 py-2 text-sm min-h-[36px]",
  md: "px-6 py-3 text-base min-h-[44px]",
  lg: "px-8 py-4 text-lg min-h-[52px]",
  xl: "px-10 py-5 text-xl min-h-[64px]",
};

export default function Button({
  children,
  variant = "primary",
  size = "lg",
  onClick,
  disabled = false,
  fullWidth = false,
  className = "",
  type = "button",
  ...props
}) {
  const baseClasses =
    "inline-flex items-center justify-center font-semibold rounded-button transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed";

  return (
    <motion.button
      type={type}
      onClick={onClick}
      disabled={disabled}
      whileTap={disabled ? {} : { scale: 0.98 }}
      whileHover={disabled ? {} : { brightness: 1.05 }}
      className={`
        ${baseClasses}
        ${variants[variant] || variants.primary}
        ${sizes[size] || sizes.lg}
        ${fullWidth ? "w-full" : ""}
        ${className}
      `}
      {...props}
    >
      {children}
    </motion.button>
  );
}
