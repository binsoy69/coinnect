import { useNavigate } from "react-router-dom";
import PageLayout from "../../components/layout/PageLayout";
import QRCodeDisplay from "../../components/ewallet/QRCodeDisplay";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";

export default function EWalletQRCodeScreen() {
  const navigate = useNavigate();
  const { ewallet, getEWalletConfig, getProviderStyles } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  const handleVerify = () => {
    navigate(getEWalletRoute(ROUTES.EWALLET_VERIFY, ewallet.serviceType));
  };

  const handleBack = () => {
    navigate(getEWalletRoute(ROUTES.EWALLET_CONFIRM, ewallet.serviceType));
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: handleBack,
        subtitle: "Scan QR Code",
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
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)] p-6">
        <QRCodeDisplay
          providerName={config.providerName}
          onVerify={handleVerify}
          colorVariant={ewallet.provider}
        />
      </div>
    </PageLayout>
  );
}
