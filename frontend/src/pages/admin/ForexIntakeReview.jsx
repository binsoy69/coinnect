import { useState } from "react";

export default function ForexIntakeReview({ intake, request, reload }) {
  const [outcome, setOutcome] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const reconcile = async () => {
    setBusy(true); setError("");
    try {
      await request(`/admin/forex-intakes/${intake.id}/reconcile`, { method: "POST",
        body: JSON.stringify({ retained: outcome === "retained", notes }) });
      await reload();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <article className="border border-amber-300 rounded-xl p-4 space-y-3">
    <h3 className="font-bold">Verify forex intake: {intake.denomination}</h3><p>{intake.transaction_id}</p>
    <label>Physical outcome <select value={outcome} onChange={e => setOutcome(e.target.value)} className="border p-2"><option value="">Select after inspection</option><option value="retained">Bill retained by kiosk</option><option value="ejected">Bill returned / not retained</option></select></label>
    <label className="block">Inspection evidence<textarea className="block border p-2" value={notes} onChange={e => setNotes(e.target.value)} maxLength={1000} /></label>
    <button className="underline disabled:opacity-40" disabled={busy || !outcome || !notes.trim()} onClick={reconcile}>Record verified outcome</button>
    {error && <p role="alert">{error}</p>}
  </article>;
}
