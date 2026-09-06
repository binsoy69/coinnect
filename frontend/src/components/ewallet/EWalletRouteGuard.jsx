import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useEWallet } from "../../context/EWalletContext";
import { ROUTES, getEWalletRoute } from "../../constants/routes";

export default function EWalletRouteGuard() {
  const { ewallet } = useEWallet();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const state = ewallet.backendState?.state;
    if (!state || pathname.startsWith("/admin")) return;
    let destination;
    if (["COMPLETE", "CLAIM_REQUIRED", "CANCELLED", "FAILED", "ABANDONED_RETAINED", "RESOLVED"].includes(state)) {
      if (state === "COMPLETE" && pathname.endsWith("/success")) return;
      destination = ROUTES.EWALLET_SUMMARY;
    } else if (state === "WAITING_FOR_PAYMENT") destination = ROUTES.EWALLET_QR;
    else if (state === "ACCEPTING_CASH") {
      if (pathname.endsWith("/insert-bills") || pathname.endsWith("/insert-coins")) return;
      destination = ROUTES.EWALLET_INSERT_BILLS;
    } else destination = ROUTES.EWALLET_PROCESSING;
    const path = getEWalletRoute(destination, ewallet.serviceType);
    if (path !== pathname) navigate(path, { replace: true });
  }, [ewallet.backendState, ewallet.serviceType, navigate, pathname]);
  return null;
}
