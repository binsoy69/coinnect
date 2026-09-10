import { useEffect, useState } from "react";

const parseTime = value => typeof value === "string" ? Date.parse(value) : NaN;

// Anchor once per server timestamp; ordinary snapshots must not restart time.
export function useDeadlineCountdown(deadline, serverTime) {
  const [clock, setClock] = useState(() => ({ serverTime, now: Number.isFinite(parseTime(serverTime)) ? parseTime(serverTime) : Date.now() }));
  useEffect(() => {
    const epoch = Number.isFinite(parseTime(serverTime)) ? parseTime(serverTime) : Date.now();
    const mono = performance.now();
    const update = () => setClock({ serverTime, now: epoch + performance.now() - mono });
    const initial = setTimeout(update, 0);
    const interval = setInterval(update, 250);
    return () => { clearTimeout(initial); clearInterval(interval); };
  }, [serverTime]);
  const now = clock.serverTime === serverTime ? clock.now : Number.isFinite(parseTime(serverTime)) ? parseTime(serverTime) : clock.now;
  const end = parseTime(deadline);
  return { secondsRemaining: Number.isFinite(end) ? Math.max(0, Math.ceil((end - now) / 1000)) : null, now };
}
