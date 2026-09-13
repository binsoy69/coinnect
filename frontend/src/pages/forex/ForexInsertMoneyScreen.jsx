import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageLayout from "../../components/layout/PageLayout";
import CashInsertionLayout from "../../components/transaction/CashInsertionLayout";
import { customerError, customerFailure } from "../../lib/customerErrors";
import Button from "../../components/common/Button";
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
        if (!resp.ok) throw customerFailure(data, resp.status);
        await refreshForexTransaction();
        if (!disposed && data.state === "WAITING_FOR_BILL") timer = setTimeout(accept, 500);
      } catch (err) { if (!disposed) setIntakeError(customerError(err)); }
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
  return <PageLayout headerProps={{ className: "flex-wrap gap-3 [&>div]:max-w-full [&>div>div]:flex-wrap", subtitle: "Foreign Exchange" }}>
    <CashInsertionLayout theme="forex" heading={config.insertHeading} note={config.insertNote}
      currency={forex.fromCurrency} inserted={forex.moneyInserted} totalDue={forex.totalDue}
      groups={[{ label: "Bills", denominations: config.acceptDenominations || [], counts: forex.insertedCounts }]}
      timing={backendState || {}} active={!backendState || backendState.state === "WAITING_FOR_BILL"}>
        <p>PHP change is accepted only when exact change is available.</p>
        <p>After cash is accepted, cancellation is disabled. Complete the exchange or wait for a refund claim when the session expires.</p>
        {backendState?.error_message && <p role="alert">{customerError(backendState)}</p>}
        {(error || intakeError) && <div role="alert"><p>{customerError(error || intakeError)}</p><Button onClick={() => { setIntakeError(null); refreshForexTransaction().catch(() => {}); }}>Retry status</Button></div>}
        {backendState?.state === "WAITING_FOR_BILL" && secondsRemaining != null && secondsRemaining <= 30 && <div><p>Your session is about to expire.</p><Button onClick={() => continueForexTransaction().catch(() => {})}>Continue</Button></div>}
        {backendState?.state === "WAITING_FOR_BILL" && forex.moneyInserted === 0 && <Button onClick={() => cancelForexTransaction().then(() => navigate(ROUTES.FOREX)).catch(() => {})}>Cancel</Button>}
    </CashInsertionLayout>
  </PageLayout>;
}
