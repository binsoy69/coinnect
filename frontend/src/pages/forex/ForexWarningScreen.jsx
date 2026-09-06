import { useNavigate } from "react-router-dom";
import { useForex } from "../../context/ForexContext";
import { ROUTES, getForexRoute } from "../../constants/routes";
import Button from "../../components/common/Button";

export default function ForexWarningScreen() {
  const navigate = useNavigate();
  const { backendState: state, forex, error, refreshForexTransaction, resetForexTransaction } = useForex();
  const terminal = ["ERROR", "CLAIM_REQUIRED", "CANCELLED", "COMPLETE", "RESOLVED"].includes(state?.state);
  return <div className="min-h-screen bg-coinnect-forex text-white flex flex-col items-center justify-center gap-6 p-8">
    <h1 className="text-3xl font-bold">{state?.claim ? "Your refund / payout claim" : terminal ? "Transaction ended" : "Checking transaction status"}</h1>
    <p role="alert">{error || state?.error_message}</p>
    {state?.claim && <div className="bg-white/10 rounded-xl p-6 space-y-3"><p className="text-3xl font-mono">{state.claim.claim_ticket_code}</p>
      {state.claim.items.map(item => <p key={item.id}>{item.kind.replaceAll("_", " ")}: {item.currency} {item.amount} — {item.status}</p>)}
      <p>Keep this reference and contact the kiosk administrator. Provisional amounts require verification.</p>
    </div>}
    <Button onClick={() => refreshForexTransaction().catch(() => {})}>Retry status</Button>
    {state?.state === "WAITING_FOR_BILL" && <Button onClick={() => navigate(getForexRoute(ROUTES.FOREX_INSERT, forex.serviceType))}>Return to insertion</Button>}
    {state?.state === "WAITING_FOR_CONFIRMATION" && <Button onClick={() => navigate(getForexRoute(ROUTES.FOREX_SUMMARY, forex.serviceType))}>Review exchange</Button>}
    {terminal && <Button onClick={() => { resetForexTransaction(); navigate(ROUTES.HOME); }}>Return home</Button>}
  </div>;
}
