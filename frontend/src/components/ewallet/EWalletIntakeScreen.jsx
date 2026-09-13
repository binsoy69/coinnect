import { customerError } from "../../lib/customerErrors";
import CashInsertionLayout from "../transaction/CashInsertionLayout";
import { useEffect, useState } from "react";
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
  const [intakeError, setIntakeError] = useState("");
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
        if (!stopped) { syncBackendState(data); setIntakeError(""); }
      } catch (failure) {
        if (!stopped) setIntakeError(customerError(failure));
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
  const state = ewallet.backendState || {};
  const provider = ewallet.provider || "gcash";
  const bills = {}, coins = {};
  Object.entries(state.intake_counts || {}).forEach(([key, count]) => {
    const [kind, denomination] = key.split(":");
    (kind === "COIN" ? coins : bills)[denomination] = count;
  });
  return <PageLayout headerProps={{ className: "flex-wrap gap-3 [&>div]:max-w-full [&>div>div]:flex-wrap", showBack: false, subtitle: "E-Wallet", rightContent:
    <span className="font-bold text-lg">{provider === "maya" ? "Maya" : "GCash"} Cash In</span> }}>
    <CashInsertionLayout theme={provider} medium={billMode ? "bill" : "coin"}
      heading={billMode ? "Please Insert Bills" : "Please Insert Coins"}
      note={billMode ? "Ensure your bill is in the correct orientation and in good condition. Insert one bill at a time." : "Insert coins one at a time. Wait for each coin to be counted."}
      inserted={state.inserted_amount || 0} totalDue={state.total_due || 0}
      timing={state} active={active}
      groups={[{ label: "Bills", denominations: [20, 50, 100, 200, 500, 1000], counts: bills },
        { label: "Coins", denominations: [1, 5, 10, 20], counts: coins }]}
      actions={<button disabled={!active || isSorting || (billMode ? !coinSafe : !state.allowed_intake?.bills?.length)}
        className="rounded-button border-2 border-gray-500 px-6 py-3 disabled:opacity-40"
        onClick={() => navigate(getEWalletRoute(billMode ? ROUTES.EWALLET_INSERT_COINS : ROUTES.EWALLET_INSERT_BILLS, ewallet.serviceType))}>
        {billMode ? "Insert coins instead" : "Insert bills instead"}
      </button>}>
      <p>Wallet credit: ₱{state.transfer_amount || 0} · Fee: ₱{state.fee || 0} · Remaining: ₱{Math.max(0, (state.total_due || 0) - (state.inserted_amount || 0))}</p>
      <p>Coin change: ₱{state.change_due || 0}. Change is available in coins only, up to ₱20, subject to stock. Bills requiring more change will be returned.</p>
      <p>Accepted bills: {state.allowed_intake?.bills?.map(value => `₱${value}`).join(", ") || "None"}. Coins: {coinSafe ? "available" : "unavailable"}.</p>
      <EWalletSessionStatus compact />
      {!billMode && intakeError && <p role="alert">{intakeError}</p>}
      {lastError && <div role="alert" className="rounded-xl bg-red-50 p-4 text-red-800"><p>{customerError(lastError)}</p><button className="mt-3 border rounded-lg px-6 py-3" onClick={clearError}>Try again</button></div>}
      <p>Processing starts automatically when sufficient cash is accepted.</p>
    </CashInsertionLayout>
    <SortingOverlay isOpen={isSorting} />
  </PageLayout>;
}
