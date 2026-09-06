import { useEWallet } from "../../context/EWalletContext";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../constants/routes";
export default function EWalletProcessingScreen() {
  const { ewallet, resetTransaction } = useEWallet();
  const navigate = useNavigate();
  const cancelling = ewallet.backendState?.state === "CANCELLATION_PENDING";
  return <main className="min-h-screen flex flex-col items-center justify-center p-8">
    <LoadingSpinner text={cancelling ? "Checking payment cancellation…" : "Processing your transaction…"} />
    <p className="mt-6">Keep this screen open. Do not insert more money.</p>
    {!cancelling && <p>Wallet transfers may take up to 20 minutes. An unresolved transfer will receive a provisional claim reference.</p>}
    {ewallet.gatewayError && <p role="status" className="mt-4">{ewallet.gatewayError}</p>}
    {cancelling && ewallet.backendState?.session_closed && <>
      <p>Payment status will continue to be checked. Keep reference {ewallet.transactionId} if your wallet was charged.</p>
      <button className="mt-4 rounded-lg border px-6 py-3" onClick={() => { resetTransaction(); navigate(ROUTES.HOME); }}>Return home</button>
    </>}
  </main>;
}
