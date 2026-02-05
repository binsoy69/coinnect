import { motion } from 'framer-motion';

export default function LoadingDots({ count = 5, color = 'white', className = '' }) {
  const dotVariants = {
    initial: { y: 0 },
    animate: { y: [-20, 0, -20] },
  };

  const colorClasses = {
    white: 'bg-white',
    orange: 'bg-coinnect-primary',
    gray: 'bg-gray-400',
  };

  return (
    <div className={`flex items-center justify-center gap-3 ${className}`}>
      {Array.from({ length: count }).map((_, index) => (
        <motion.div
          key={index}
          className={`w-4 h-4 rounded-full ${colorClasses[color] || colorClasses.white}`}
          variants={dotVariants}
          initial="initial"
          animate="animate"
          transition={{
            duration: 0.6,
            repeat: Infinity,
            repeatType: 'loop',
            delay: index * 0.1,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  );
}
