import { useState } from "react";
import { useEWallet } from "../../context/EWalletContext";

import DeadlineCountdown from "../common/DeadlineCountdown";
import { useDeadlineCountdown } from "../../hooks/useDeadlineCountdown";

export default function EWalletSessionStatus() {
  const { ewallet, continueSession, cancelBackendTransaction } = useEWallet();
  const [error, setError] = useState("");
  const state = ewallet.backendState;
  const { secondsRemaining: seconds } = useDeadlineCountdown(state?.deadline, state?.server_time);
  if (!state) return null;
  const waiting = ["ACCEPTING_CASH", "WAITING_FOR_PAYMENT"].includes(state.state);
  return <section className="my-4 rounded-xl border border-amber-400 bg-amber-50 p-4 text-gray-900">
    {state.direction === "cash-out" && <p>Amount paid: ₱{state.amount} · Fee: ₱{state.fee} · Cash received: ₱{state.transfer_amount}</p>}
    {state.direction === "cash-in" && <>
      <p>Due: ₱{state.total_due} · Accepted: ₱{state.inserted_amount} · Remaining: ₱{Math.max(0, state.total_due-state.inserted_amount)}</p>
      <p>Coin change: ₱{state.change_due || 0} · Maximum change: ₱20</p>
      <p>Accepted bills: {state.allowed_intake?.bills?.map(value => `₱${value}`).join(", ") || "None"}. Coins: {state.allowed_intake?.coins_enabled ? "available" : "unavailable"}.</p>
    </>}
    {state.direction === "cash-in" && <DeadlineCountdown deadline={state.deadline} serverTime={state.server_time}
      durationSeconds={state.inactivity_timeout_seconds} active={waiting} />}
    {waiting && <>
      {state.direction === "cash-out" && <p className="font-bold">{seconds === null ? "Checking session…" : seconds > 0 ? `${seconds}s remaining` : "Closing intake and checking your transaction…"}</p>}
      {seconds !== null && seconds <= 30 && state.direction === "cash-in" && state.inserted_amount > 0 && <p>Tap Continue now. On inactivity expiry, partial cash is retained without wallet credit or a claim.</p>}
      {seconds !== null && seconds <= 30 && state.direction === "cash-out" && <p>This QR session closes in {seconds} seconds. Payment status will be checked before cancellation is confirmed.</p>}
      {state.direction === "cash-in" && <button className="m-2 rounded-lg bg-gray-900 px-6 py-3 text-white" onClick={() => continueSession().catch(e => setError(e.message))}>Continue</button>}
    </>}
    {state.can_cancel && <button className="m-2 rounded-lg border border-gray-700 px-6 py-3" onClick={() => cancelBackendTransaction().catch(e => setError(e.message))}>Cancel before payment</button>}
    {!state.can_cancel && waiting && <p>Cash received. Cancellation is unavailable.</p>}
    {(error || ewallet.gatewayError) && <p role="alert">{error || ewallet.gatewayError}</p>}
  </section>;
}
