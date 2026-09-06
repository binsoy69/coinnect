import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageLayout from "../../components/layout/PageLayout";
import Button from "../../components/common/Button";
import InsertMoneyPanel from "../../components/transaction/InsertMoneyPanel";
import { ROUTES, getForexRoute } from "../../constants/routes";
import { useForex } from "../../context/ForexContext";
import { API_BASE, ENABLE_KEYBOARD_SIM } from "../../constants/api";

export default function ForexInsertMoneyScreen() {
  const navigate = useNavigate();
  const { forex, transactionId, backendState, getForexConfig, secondsRemaining, error,
    refreshForexTransaction, continueForexTransaction, cancelForexTransaction, simulateForexInsert } = useForex();
  const [intakeError, setIntakeError] = useState(null);
  const accepting = useRef(false);
  const config = getForexConfig();
  useEffect(() => {
    if (!transactionId || backendState?.state !== "WAITING_FOR_BILL" || intakeError) return undefined;
    let disposed = false;
    let timer;
    const accept = async () => {
      if (accepting.current) { timer = setTimeout(accept, 500); return; }
      accepting.current = true;
      try {
        const resp = await fetch(`${API_BASE}/forex/transaction/${transactionId}/accept-bill`, { method: "POST" });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail?.message || data.detail || "Bill acceptance unavailable");
        await refreshForexTransaction();
        if (!disposed && data.state === "WAITING_FOR_BILL") timer = setTimeout(accept, 500);
      } catch (err) { if (!disposed) setIntakeError(err.message); }
      finally { accepting.current = false; }
    };
    timer = setTimeout(accept, 0);
    return () => { disposed = true; clearTimeout(timer); };
  }, [transactionId, backendState?.state, refreshForexTransaction, intakeError]);
  useEffect(() => {
    if (backendState?.state === "WAITING_FOR_CONFIRMATION") navigate(getForexRoute(ROUTES.FOREX_CONVERSION, forex.serviceType));
    if (["ERROR", "CLAIM_REQUIRED", "CANCELLED"].includes(backendState?.state)) navigate(getForexRoute(ROUTES.FOREX_WARNING, forex.serviceType));
  }, [backendState?.state, navigate, forex.serviceType]);
  useEffect(() => {
    if (!ENABLE_KEYBOARD_SIM || !transactionId || !config) return undefined;
    const key = e => {
      const value = config.acceptDenominations[Number(e.key)-1];
      if (value) simulateForexInsert(value, forex.fromCurrency).catch(() => {});
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [transactionId, config, simulateForexInsert, forex.fromCurrency]);
  if (!config) return <p>Restoring forex transaction…</p>;
  return <PageLayout headerProps={{ subtitle: "Foreign Exchange" }}>
    <div className="flex gap-8 p-8">
      <div className="w-1/3"><InsertMoneyPanel variant="bill" cardVariant="forex" noteText={config.insertNote} /></div>
      <div className="flex-1 text-center space-y-6">
        <h1 className="text-3xl font-bold">{config.insertHeading}</h1>
        <p className="text-5xl font-bold">{forex.fromCurrency} {forex.moneyInserted}</p>
        <p className="text-2xl">Total due: {forex.fromCurrency} {forex.totalDue}</p>
        <p>PHP change is accepted only when exact change is available.</p>
        <p>After cash is accepted, cancellation is disabled. Complete the exchange or wait for a refund claim when the session expires.</p>
        {backendState?.error_message && <p role="alert">{backendState.error_message}</p>}
        {(error || intakeError) && <div role="alert"><p>{error || intakeError}</p><Button onClick={() => { setIntakeError(null); refreshForexTransaction().catch(() => {}); }}>Retry status</Button></div>}
        <p aria-live="polite">{secondsRemaining == null ? "Checking session…" : `${secondsRemaining} seconds remaining`}</p>
        {secondsRemaining != null && secondsRemaining <= 30 && <div><p>Your session is about to expire.</p><Button onClick={() => continueForexTransaction().catch(() => {})}>Continue</Button></div>}
        {forex.moneyInserted === 0 && <Button onClick={() => cancelForexTransaction().then(() => navigate(ROUTES.FOREX)).catch(() => {})}>Cancel</Button>}
      </div>
    </div>
  </PageLayout>;
}
