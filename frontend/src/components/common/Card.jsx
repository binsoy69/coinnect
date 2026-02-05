import { motion } from "framer-motion";

const variants = {
  default: "bg-surface-white shadow-sm",
  orange: "bg-coinnect-primary text-white",
  forex: "bg-coinnect-forex text-white",
  outlined: "bg-transparent border-2 border-gray-300",
};

export default function Card({
  children,
  variant = "default",
  onClick,
  className = "",
  animated = true,
  ...props
}) {
  const isClickable = !!onClick;

  const baseClasses = "rounded-card";
  const clickableClasses = isClickable ? "cursor-pointer" : "";

  const Component = animated ? motion.div : "div";

  const animationProps =
    animated && isClickable
      ? {
          whileHover: { scale: 1.02, y: -4 },
          whileTap: { scale: 0.98 },
          transition: { duration: 0.2 },
        }
      : {};

  return (
    <Component
      onClick={onClick}
      className={`
        ${baseClasses}
        ${variants[variant] || variants.default}
        ${clickableClasses}
        ${className}
      `}
      {...animationProps}
      {...props}
    >
      {children}
    </Component>
  );
}
