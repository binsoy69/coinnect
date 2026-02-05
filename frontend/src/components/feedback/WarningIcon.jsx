import { motion } from 'framer-motion';

export default function WarningIcon({ size = 150, className = '' }) {
  const containerVariants = {
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

  const exclamationVariants = {
    hidden: { opacity: 0, y: -10 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        delay: 0.2,
        duration: 0.3,
      },
    },
  };

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      className={`relative ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Background circle */}
      <div className="absolute inset-0 rounded-full bg-coinnect-warning" />

      {/* Exclamation mark */}
      <motion.div
        variants={exclamationVariants}
        className="absolute inset-0 flex flex-col items-center justify-center text-white"
      >
        {/* Main line */}
        <div
          className="bg-white rounded-full"
          style={{
            width: size * 0.1,
            height: size * 0.35,
            marginBottom: size * 0.08,
          }}
        />
        {/* Dot */}
        <div
          className="bg-white rounded-full"
          style={{
            width: size * 0.12,
            height: size * 0.12,
          }}
        />
      </motion.div>
    </motion.div>
  );
}
