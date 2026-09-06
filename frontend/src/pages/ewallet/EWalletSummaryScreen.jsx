import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useEWallet } from "../../context/EWalletContext";
import { ROUTES } from "../../constants/routes";

export default function EWalletSummaryScreen() {
  const { ewallet, resetTransaction } = useEWallet();
  const navigate = useNavigate();
  const state = ewallet.backendState;
  const retained = state?.state === "ABANDONED_RETAINED";
  const cancelled = state?.state === "CANCELLED";
  useEffect(() => {
    if (!retained && !cancelled) return;
    const timer = setTimeout(() => { resetTransaction(); navigate(ROUTES.HOME); }, 8000);
    return () => clearTimeout(timer);
  }, [retained, cancelled, resetTransaction, navigate]);
  if (!state) return null;
  const title = state.state === "COMPLETE" ? "Transaction complete"
    : retained ? "Session expired" : cancelled ? "Transaction cancelled" : "Operator assistance required";
  return <main className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-8">
    <section className="w-full max-w-2xl rounded-xl bg-white p-8 space-y-4">
      <h1 className="text-3xl font-bold">{title}</h1>
      <p>Reference: {state.transaction_id}</p>
      {retained ? <p>₱{state.retained_amount} was retained after partial-payment inactivity. No wallet credit or claim ticket was issued.</p> : <>
        <p>Total: ₱{state.amount} · Fee: ₱{state.fee} · Fee refunded/owed: ₱{state.refunded_fee || 0}</p>
        <p>Cash accepted: ₱{state.inserted_amount} · Wallet credited: ₱{state.wallet_credited || 0}</p>
        <p>Cash dispensed: ₱{state.dispensed_amount} · Change returned: ₱{state.change_dispensed || 0}</p>
      </>}
      {state.claim_ticket_code && <p className="font-bold">Claim reference: {state.claim_ticket_code}</p>}
      {state.claims?.map(claim => <p key={claim.claim_ticket_code}>₱{claim.amount} · {claim.status === "PROVISIONAL" ? "Pending verification — amount is provisional" : "Operator settlement required"}</p>)}
      {state.error_message && <p role="status">{state.error_message}</p>}
      <button className="rounded-lg bg-gray-900 text-white px-8 py-4" onClick={() => { resetTransaction(); navigate(ROUTES.HOME); }}>Finish</button>
    </section>
  </main>;
}
