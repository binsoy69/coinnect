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
    navigate(getEWalletRoute(ROUTES.EWALLET_DETAILS, ewallet.serviceType));
  };

  const handleProceed = () => {
    navigate(getEWalletRoute(ROUTES.EWALLET_SUCCESS, ewallet.serviceType));
  };

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-8">
      <EWalletTransactionCard
        serviceName={config.displayName}
        mobileNumber={ewallet.mobileNumber}
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
        provider={config.provider}
      />
    </div>
  );
}
