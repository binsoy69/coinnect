import { useNavigate } from "react-router-dom";
import EWalletTransactionCard from "../../components/ewallet/EWalletTransactionCard";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import { isCashOut } from "../../constants/ewalletData";

export default function EWalletSummaryScreen() {
  const navigate = useNavigate();
  const { ewallet, getEWalletConfig } = useEWallet();
  const config = getEWalletConfig();

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  const handleBack = () => {
    navigate(ROUTES.EWALLET);
  };

  const handleProceed = () => {
    if (requiresClaim || ewallet.backendState?.state === "FAILED") {
      navigate(ROUTES.HOME);
      return;
    }
    navigate(getEWalletRoute(ROUTES.EWALLET_SUCCESS, ewallet.serviceType));
  };

  const requiresClaim = ewallet.backendState?.state === "CLAIM_REQUIRED";

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-8">
      <EWalletTransactionCard
        serviceName={config.displayName}
        mobileNumber={ewallet.mobileNumber}
        accountName={ewallet.accountName}
        totalInserted={
          isCashOut(ewallet.serviceType)
            ? ewallet.totalDue
            : ewallet.totalInserted
        }
        fee={ewallet.fee}
        transferAmount={ewallet.transferAmount}
        totalDue={ewallet.totalDue}
        onBack={handleBack}
        onProceed={handleProceed}
        proceedLabel={
          requiresClaim || ewallet.backendState?.state === "FAILED"
            ? "Exit"
            : "Proceed"
        }
        provider={config.provider}
      />
      {requiresClaim && (
        <div className="mt-6 max-w-md w-full bg-amber-100 border border-amber-400 rounded-xl p-5 text-center">
          <h2 className="font-bold text-amber-900 text-xl">
            Operator assistance required
          </h2>
          <p className="text-amber-800 mt-2">
            Claim ticket:{" "}
            <strong>{ewallet.backendState?.claim_ticket_code}</strong>
          </p>
          <p className="text-sm text-amber-700 mt-2">
            Keep this reference and contact the kiosk operator.
          </p>
        </div>
      )}
    </div>
  );
}
