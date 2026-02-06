import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import { EWALLET_TIMER_DURATIONS } from "../../constants/ewalletData";

export default function EWalletProcessingScreen() {
  const navigate = useNavigate();
  const { ewallet, getEWalletConfig, getProviderStyles } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();

  useEffect(() => {
    if (!config) {
      navigate(ROUTES.EWALLET);
      return;
    }

    const timer = setTimeout(() => {
      navigate(getEWalletRoute(ROUTES.EWALLET_SUMMARY, ewallet.serviceType));
    }, EWALLET_TIMER_DURATIONS.AUTO_ADVANCE);

    return () => clearTimeout(timer);
  }, [config, navigate, ewallet.serviceType]);

  if (!config) {
    return null;
  }

  return (
    <div
      className={`min-h-screen ${styles.bg} flex flex-col items-center justify-center`}
    >
      <LoadingSpinner text="Checking..." size={120} />
    </div>
  );
}
