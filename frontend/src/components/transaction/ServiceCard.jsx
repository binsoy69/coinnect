import { motion } from 'framer-motion';

export default function ServiceCard({
  icon,
  title,
  description,
  color = 'bg-coinnect-primary',
  onClick,
  disabled = false,
  className = '',
}) {
  return (
    <motion.div
      onClick={disabled ? undefined : onClick}
      whileHover={disabled ? {} : { scale: 1.03, y: -4 }}
      whileTap={disabled ? {} : { scale: 0.98 }}
      className={`
        ${color}
        rounded-card p-8 text-white text-center cursor-pointer
        transition-all duration-200
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${className}
      `}
    >
      {icon && (
        <div className="flex justify-center mb-4">
          <img
            src={icon}
            alt={title}
            className="w-20 h-20 object-contain"
          />
        </div>
      )}
      <h3 className="text-xl font-bold mb-2">{title}</h3>
      {description && (
        <p className="text-white/80 text-sm">{description}</p>
      )}
    </motion.div>
  );
}
