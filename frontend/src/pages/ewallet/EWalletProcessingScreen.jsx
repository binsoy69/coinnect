import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import { EWALLET_TIMER_DURATIONS } from "../../constants/ewalletData";

export default function EWalletProcessingScreen() {
  const navigate = useNavigate();
  const {
    ewallet,
    getEWalletConfig,
    getProviderStyles,
    confirmBackendTransaction,
    refreshBackendTransaction,
  } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();

  useEffect(() => {
    if (!config) {
      navigate(ROUTES.EWALLET);
      return;
    }

    let cancelled = false;
    let interval;
    const process = async () => {
      await confirmBackendTransaction().catch(() => null);
      interval = setInterval(async () => {
        const data = await refreshBackendTransaction().catch(() => null);
        if (
          !cancelled &&
          ["COMPLETE", "CLAIM_REQUIRED", "FAILED"].includes(data?.state)
        ) {
          clearInterval(interval);
          navigate(getEWalletRoute(ROUTES.EWALLET_SUMMARY, ewallet.serviceType));
        }
      }, EWALLET_TIMER_DURATIONS.AUTO_ADVANCE);
    };
    process();
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [
    config,
    confirmBackendTransaction,
    ewallet.serviceType,
    navigate,
    refreshBackendTransaction,
  ]);

  if (!config) {
    return null;
  }

  return (
    <div
      className={`min-h-screen ${styles.bg} flex flex-col items-center justify-center`}
    >
      <LoadingSpinner
        text={
          ewallet.backendState?.state === "DISBURSEMENT_PENDING"
            ? "Sending wallet credit..."
            : "Checking..."
        }
        size={120}
      />
    </div>
  );
}
