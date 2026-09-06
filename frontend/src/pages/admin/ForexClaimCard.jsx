import { useState } from "react";

export default function ForexClaimCard({ claim, request, reload }) {
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const resolve = async item => {
    setBusy(true); setError("");
    try {
      await request(`/admin/forex-claims/${claim.claim_ticket_code}/items/${item.id}/resolve`, {
        method: "POST", body: JSON.stringify({ resolution_notes: notes }),
      });
      await reload();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <article className="rounded-xl border bg-white p-6 space-y-4">
    <h3 className="text-xl font-bold">Forex claim {claim.claim_ticket_code}</h3>
    <p>{claim.transaction_id} — {claim.reason_message}</p>
    {claim.items.map(item => <div key={item.id} className="flex justify-between gap-4">
      <span>{item.kind.replaceAll("_", " ")}: {item.currency} {item.amount} ({item.status})</span>
      <button className="underline disabled:opacity-40" disabled={busy || !notes.trim() || item.status !== "OPEN"} onClick={() => resolve(item)}>Record settlement</button>
    </div>)}
    <label className="block">Settlement evidence and notes<textarea value={notes} onChange={e => setNotes(e.target.value)} className="block border p-2 w-full" maxLength={1000} /></label>
    <p>Provisional items require physical reconciliation before settlement.</p>
    {error && <p role="alert">{error}</p>}
  </article>;
}
