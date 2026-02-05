import { motion } from 'framer-motion';

export default function SuccessIcon({ size = 150, className = '' }) {
  const checkVariants = {
    hidden: {
      pathLength: 0,
      opacity: 0,
    },
    visible: {
      pathLength: 1,
      opacity: 1,
      transition: {
        pathLength: { duration: 0.5, ease: 'easeInOut' },
        opacity: { duration: 0.1 },
      },
    },
  };

  const circleVariants = {
    hidden: { scale: 0, opacity: 0 },
    visible: {
      scale: 1,
      opacity: 1,
      transition: {
        duration: 0.3,
        ease: 'easeOut',
      },
    },
  };

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      className={`relative ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Background circle */}
      <motion.div
        variants={circleVariants}
        className="absolute inset-0 rounded-full bg-coinnect-success"
      />

      {/* Checkmark */}
      <svg
        viewBox="0 0 100 100"
        className="absolute inset-0 w-full h-full"
      >
        <motion.path
          d="M25 50 L42 67 L75 34"
          fill="none"
          stroke="white"
          strokeWidth="8"
          strokeLinecap="round"
          strokeLinejoin="round"
          variants={checkVariants}
        />
      </svg>
    </motion.div>
  );
}
