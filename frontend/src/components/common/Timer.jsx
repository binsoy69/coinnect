import { useCountdown } from "../../hooks/useCountdown";

// Color variants with full class names for Tailwind to detect
const colorVariants = {
  primary: {
    text: "text-coinnect-primary",
    bg: "bg-coinnect-primary",
  },
  forex: {
    text: "text-coinnect-forex",
    bg: "bg-coinnect-forex",
  },
  ewallet: {
    text: "text-coinnect-ewallet",
    bg: "bg-coinnect-ewallet",
  },
  gcash: {
    text: "text-coinnect-gcash",
    bg: "bg-coinnect-gcash",
  },
  maya: {
    text: "text-coinnect-maya",
    bg: "bg-coinnect-maya",
  },
};

export default function Timer({
  seconds: initialSeconds = 60,
  onComplete,
  showProgressBar = true,
  autoStart = true,
  color = "primary", // 'primary' or 'forex'
  className = "",
}) {
  const { seconds, remainingProgress } = useCountdown(
    initialSeconds,
    onComplete,
    autoStart,
  );

  const colors = colorVariants[color] || colorVariants.primary;

  return (
    <div className={`flex flex-col items-center ${className}`}>
      {/* Seconds display */}
      <div className={`text-6xl font-bold ${colors.text} mb-4`}>{seconds}</div>

      {/* Progress bar */}
      {showProgressBar && (
        <div className="w-full max-w-md h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full ${colors.bg} rounded-full transition-all duration-1000 ease-linear`}
            style={{ width: `${remainingProgress}%` }}
          />
        </div>
      )}
    </div>
  );
}
