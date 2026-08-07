import { Navigate, useParams } from 'react-router-dom';
import { ROUTES, getServiceRoute } from '../../constants/routes';

export default function TransactionFeeScreen() {
  const { type } = useParams();
  return <Navigate replace to={getServiceRoute(ROUTES.CONFIRMATION, type)} />;
}
