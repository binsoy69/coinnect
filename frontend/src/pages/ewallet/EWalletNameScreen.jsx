import { Navigate } from "react-router-dom";
import { useEWallet } from "../../context/EWalletContext";
import { ROUTES, getEWalletRoute } from "../../constants/routes";

export default function EWalletNameScreen() {
  const { ewallet } = useEWallet();
  return <Navigate replace to={ewallet.serviceType ? getEWalletRoute(ROUTES.EWALLET_MOBILE, ewallet.serviceType) : ROUTES.EWALLET} />;
}
