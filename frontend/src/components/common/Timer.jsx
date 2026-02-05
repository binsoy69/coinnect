import { useCountdown } from '../../hooks/useCountdown';

export default function Timer({
  seconds: initialSeconds = 60,
  onComplete,
  showProgressBar = true,
  autoStart = true,
  className = '',
}) {
  const { seconds, remainingProgress } = useCountdown(initialSeconds, onComplete, autoStart);

  return (
    <div className={`flex flex-col items-center ${className}`}>
      {/* Seconds display */}
      <div className="text-6xl font-bold text-coinnect-primary mb-4">
        {seconds}
      </div>

      {/* Progress bar */}
      {showProgressBar && (
        <div className="w-full max-w-md h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-coinnect-primary rounded-full transition-all duration-1000 ease-linear"
            style={{ width: `${remainingProgress}%` }}
          />
        </div>
      )}
    </div>
  );
}
