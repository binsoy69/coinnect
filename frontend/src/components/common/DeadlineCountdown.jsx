import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";

export default function DeadlineCountdown({ deadline, serverTime, durationSeconds, active = true }) {
  const { secondsRemaining } = useDeadlineCountdown(deadline, serverTime);
  const valid = secondsRemaining !== null && Number.isFinite(durationSeconds) && durationSeconds > 0;
  const progress = valid ? Math.min(100, Math.max(0, secondsRemaining / durationSeconds * 100)) : 0;
  return <div className="w-full py-3 text-center">
    {active && valid && <>
      <div role="progressbar" aria-label="Time remaining" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}
        className="h-3 w-full overflow-hidden rounded-full bg-white">
        <div className="h-full rounded-full bg-coinnect-primary transition-[width] duration-200 motion-reduce:transition-none" style={{ width: `${progress}%` }} />
      </div>
      <div role="timer" aria-label="Time remaining" aria-live="off" className="mt-3 text-3xl font-bold tabular-nums text-gray-900">{secondsRemaining}s</div>
    </>}
    <p className="mt-3 text-sm text-gray-500">{!active ? "Processing your transaction…" : !valid ? "Checking session…" : secondsRemaining === 0 ? "Checking transaction status…" : "Insert money before the timer runs out."}</p>
  </div>;
}
