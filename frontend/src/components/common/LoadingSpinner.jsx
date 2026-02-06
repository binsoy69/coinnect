import { motion } from "framer-motion";

export default function LoadingSpinner({
  text = "Checking...",
  size = 120,
  className = "",
}) {
  const dotCount = 8;
  const radius = size / 2.5;

  // Generate dots with varying sizes and opacities
  const dots = Array.from({ length: dotCount }, (_, i) => {
    const angle = (i * 360) / dotCount - 90; // Start from top
    const rad = (angle * Math.PI) / 180;
    const x = Math.cos(rad) * radius;
    const y = Math.sin(rad) * radius;

    // Largest at top (index 0), smallest at bottom (index 4)
    const sizeFactor = 1 - (i / dotCount) * 0.6;
    const dotSize = Math.max(8, 20 * sizeFactor);
    const opacity = 1 - (i / dotCount) * 0.6;

    return { x, y, dotSize, opacity, key: i };
  });

  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      {/* Spinner container */}
      <motion.div
        animate={{ rotate: 360 }}
        transition={{
          duration: 1.2,
          repeat: Infinity,
          ease: "linear",
        }}
        className="relative"
        style={{ width: size, height: size }}
      >
        {dots.map((dot) => (
          <div
            key={dot.key}
            className="absolute bg-white rounded-full"
            style={{
              width: dot.dotSize,
              height: dot.dotSize,
              opacity: dot.opacity,
              left: size / 2 + dot.x - dot.dotSize / 2,
              top: size / 2 + dot.y - dot.dotSize / 2,
            }}
          />
        ))}
      </motion.div>

      {/* Text */}
      {text && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="text-white text-2xl font-semibold mt-8"
        >
          {text}
        </motion.p>
      )}
    </div>
  );
}
