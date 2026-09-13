import InsertMoneyPanel from "./InsertMoneyPanel";
import DeadlineCountdown from "../common/DeadlineCountdown";

const colors = { gcash: "#007DFE", maya: "#01B463", forex: "#DC2626" };
export default function CashInsertionLayout({ theme = "gcash", medium = "bill", heading, note,
  currency = "PHP", inserted = 0, totalDue = 0, groups = [], timing = {}, active,
  children, actions }) {
  const accent = colors[theme] || colors.gcash;
  const money = value => !Number.isFinite(value) ? "—" : new Intl.NumberFormat("en-PH", { style: "currency", currency,
    minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(value);
  return <div className="py-2">
    <div className="flex flex-col md:flex-row gap-6 min-h-[calc(100dvh-140px)]">
      <aside className="flex-none w-full md:w-64 lg:w-72">
        <InsertMoneyPanel variant={medium} cardVariant={theme} noteText={note} className="h-full" />
      </aside>
      <section className="flex-1 min-w-0 flex flex-col items-center text-center gap-3 py-2">
        <div>
          <h1 className="text-2xl lg:text-3xl font-bold mb-1" style={{ color: accent }}>{heading}</h1>
          <p className="text-lg font-bold text-gray-900">Current Count</p>
          <p className="text-[clamp(3rem,6vw,5rem)] font-black tabular-nums leading-tight text-gray-900 break-all">{money(inserted)}</p>
          <p className="inline-block border-2 rounded-xl px-6 py-2 mt-2 text-xl" style={{ borderColor: accent, color: accent }}>Total Due: <strong>{money(totalDue)}</strong></p>
        </div>
        <div className="w-full space-y-2">
          {groups.map(group => <div key={group.label} className="flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-base">
            <span className="font-semibold text-gray-600">{group.label}</span>
            {group.denominations.map(denom => <span key={denom} className="tabular-nums"><strong>{money(denom)}</strong> = {group.counts?.[denom] || 0}x</span>)}
          </div>)}
        </div>
        <div className="w-full text-sm text-gray-700 space-y-2">{children}</div>
        <div className="w-full mt-auto">
          <DeadlineCountdown deadline={timing.deadline} serverTime={timing.server_time}
            durationSeconds={timing.inactivity_timeout_seconds} active={active} accentColor={accent} compact />
          <div className="flex flex-wrap justify-center gap-3 mt-2">{actions}</div>
        </div>
      </section>
    </div>
  </div>;
}
