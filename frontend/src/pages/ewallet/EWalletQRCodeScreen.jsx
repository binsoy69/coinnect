import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageLayout from "../../components/layout/PageLayout";
import QRCodeDisplay from "../../components/ewallet/QRCodeDisplay";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import EWalletSessionStatus from "../../components/ewallet/EWalletSessionStatus";

export default function EWalletQRCodeScreen() {
  const navigate = useNavigate();
  const {
    ewallet,
    getEWalletConfig,
    getProviderStyles,
    refreshBackendTransaction,
  } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const expired = ewallet.backendState?.deadline && now >= Date.parse(ewallet.backendState.deadline);

  const handleVerify = async () => {
    const data = await refreshBackendTransaction();
    if (
      ["COMPLETE", "CLAIM_REQUIRED", "FAILED", "CANCELLED"].includes(
        data?.state,
      )
    ) {
      navigate(getEWalletRoute(ROUTES.EWALLET_SUMMARY, ewallet.serviceType));
    }
  };

  useEffect(() => {
    const interval = setInterval(async () => {
      const data = await refreshBackendTransaction().catch(() => null);
      if (
        ["COMPLETE", "CLAIM_REQUIRED", "FAILED", "CANCELLED"].includes(
          data?.state,
        )
      ) {
        clearInterval(interval);
        navigate(getEWalletRoute(ROUTES.EWALLET_SUMMARY, ewallet.serviceType));
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [ewallet.serviceType, navigate, refreshBackendTransaction]);

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  return (
    <PageLayout
      headerProps={{
        showBack: false,
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
        <EWalletSessionStatus />
        {expired ? <p role="status" className="rounded-xl bg-amber-50 p-6 text-xl">QR session expired. Checking payment status…</p> : <QRCodeDisplay
          providerName={config.providerName}
          onVerify={handleVerify}
          colorVariant={ewallet.provider}
          qrImageUrl={ewallet.backendState?.qr_image_url}
          statusText={
            ["paid", "succeeded"].includes(
              ewallet.backendState?.gateway_status,
            )
              ? "Payment confirmed. Preparing cash."
              : "Pay with any QR Ph-compatible wallet."
          }
        />}
      </div>
    </PageLayout>
  );
}
