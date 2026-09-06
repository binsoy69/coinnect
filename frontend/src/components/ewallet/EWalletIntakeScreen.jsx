import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useEWallet } from "../../context/EWalletContext";
import { useBillAcceptance } from "../../hooks/useBillAcceptance";
import { walletRequest } from "../../lib/ewalletApi";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { ENABLE_KEYBOARD_SIM } from "../../constants/api";
import PageLayout from "../layout/PageLayout";
import EWalletSessionStatus from "./EWalletSessionStatus";
import SortingOverlay from "../transaction/SortingOverlay";

export default function EWalletIntakeScreen({ medium }) {
  const { ewallet, syncBackendState, simulateCashInsert } = useEWallet();
  const navigate = useNavigate();
  const active = ewallet.backendState?.state === "ACCEPTING_CASH";
  const billMode = medium === "bills";
  const { isSorting, lastError, clearError } = useBillAcceptance(ewallet.transactionId,
    "/ewallet/transactions", active && billMode && Boolean(ewallet.backendState?.allowed_intake?.bills?.length), syncBackendState);
  const coinSafe = ewallet.backendState?.allowed_intake?.coins_enabled;
  useEffect(() => {
    if (billMode || !active || !coinSafe || !ewallet.transactionId) return;
    let stopped = false;
    let timer;
    const open = async () => {
      try {
        const data = await walletRequest(`/ewallet/transactions/${ewallet.transactionId}/coins`, { method: "POST" });
        if (!stopped) syncBackendState(data);
      } finally { if (!stopped) timer = setTimeout(() => open().catch(() => {}), 2000); }
    };
    open().catch(() => {});
    return () => { stopped = true; clearTimeout(timer); };
  }, [active, billMode, coinSafe, ewallet.transactionId, syncBackendState]);
  useEffect(() => {
    if (!ENABLE_KEYBOARD_SIM) return;
    const handler = event => {
      const value = (billMode ? [20, 50, 100, 200, 500, 1000] : [1, 5, 10, 20])[Number(event.key)-1];
      if (value && active) simulateCashInsert(value).catch(() => {});
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [active, billMode, simulateCashInsert]);
  return <PageLayout headerProps={{ showBack: false, subtitle: `Insert ${medium}` }}>
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-bold mb-4">Insert {medium}</h1>
      <p>Wallet credit: ₱{ewallet.transferAmount} · Fee: ₱{ewallet.fee}</p>
      <p className="mt-3">Change is available in coins only, up to ₱20, subject to available stock. Bills requiring more change will be returned.</p>
      <EWalletSessionStatus />
      {lastError && <div role="alert" className="rounded-xl bg-red-50 p-4 text-red-800"><p>{lastError}</p><button className="mt-3 border rounded-lg px-6 py-3" onClick={clearError}>Try again</button></div>}
      <button disabled={billMode && !coinSafe} className="mt-4 rounded-lg border px-6 py-3 disabled:opacity-40"
        onClick={() => navigate(getEWalletRoute(billMode ? ROUTES.EWALLET_INSERT_COINS : ROUTES.EWALLET_INSERT_BILLS, ewallet.serviceType))}>
        {billMode ? "Insert coins instead" : "Insert bills instead"}
      </button>
      <p className="mt-4">Processing starts automatically when sufficient cash is accepted.</p>
    </main>
    <SortingOverlay isOpen={isSorting} />
  </PageLayout>;
}
