import { useNavigate } from "react-router-dom";
import PageLayout from "../../components/layout/PageLayout";
import AccountDetailsPanel from "../../components/ewallet/AccountDetailsPanel";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import { isCashOut } from "../../constants/ewalletData";

export default function EWalletAccountDetailsScreen() {
  const navigate = useNavigate();
  const { ewallet, getEWalletConfig, getProviderStyles } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  const handleProceed = () => {
    navigate(getEWalletRoute(ROUTES.EWALLET_PROCESSING, ewallet.serviceType));
  };

  const handleBack = () => {
    if (isCashOut(ewallet.serviceType)) {
      navigate(getEWalletRoute(ROUTES.EWALLET_VERIFY, ewallet.serviceType));
    } else {
      navigate(
        getEWalletRoute(ROUTES.EWALLET_INSERT_BILLS, ewallet.serviceType),
      );
    }
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: handleBack,
        subtitle: "Account Details",
        rightContent: (
          <div
            className={`flex items-center gap-2 ${styles.bg} text-white px-3 py-1 rounded-full text-sm`}
          >
            <img src={config.icon} alt={config.name} className="w-5 h-5" />
            E-Wallet / {config.displayName}
          </div>
        ),
      }}
    >
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)] p-8">
        <AccountDetailsPanel
          moneyInserted={
            isCashOut(ewallet.serviceType)
              ? ewallet.totalDue
              : ewallet.totalInserted
          }
          fee={ewallet.fee}
          billerNumber={ewallet.billerNumber}
          mobileNumber={ewallet.mobileNumber}
          transferAmount={ewallet.transferAmount}
          providerName={config.providerName}
          isCashOut={isCashOut(ewallet.serviceType)}
          onProceed={handleProceed}
          colorVariant={ewallet.provider}
          className="max-w-4xl"
        />
      </div>
    </PageLayout>
  );
}
