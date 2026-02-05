import { Routes, Route } from 'react-router-dom';
import { ROUTES } from '../constants/routes';

// Pages - Initial and Transaction Type
import InitialScreen from '../pages/InitialScreen';
import TransactionTypeScreen from '../pages/TransactionTypeScreen';

// Money Converter Pages
import ServiceSelectionScreen from '../pages/money-converter/ServiceSelectionScreen';
import ReminderScreen from '../pages/money-converter/ReminderScreen';
import SelectAmountScreen from '../pages/money-converter/SelectAmountScreen';
import SelectDispenseScreen from '../pages/money-converter/SelectDispenseScreen';
import TransactionFeeScreen from '../pages/money-converter/TransactionFeeScreen';
import ConfirmationScreen from '../pages/money-converter/ConfirmationScreen';
import InsertMoneyScreen from '../pages/money-converter/InsertMoneyScreen';
import TransactionSummaryScreen from '../pages/money-converter/TransactionSummaryScreen';
import ProcessingScreen from '../pages/money-converter/ProcessingScreen';
import SuccessScreen from '../pages/money-converter/SuccessScreen';
import WarningScreen from '../pages/money-converter/WarningScreen';

// Forex Pages
import {
  ForexServiceSelectionScreen,
  ForexReminderScreen,
  ExchangeRateScreen,
  ForexConfirmationScreen,
  ForexInsertMoneyScreen,
  ForexConversionScreen,
  ForexSummaryScreen,
  ForexProcessingScreen,
  ForexSuccessScreen,
  ForexWarningScreen,
} from '../pages/forex';

export default function AppRoutes() {
  return (
    <Routes>
      {/* Initial Flow */}
      <Route path={ROUTES.HOME} element={<InitialScreen />} />
      <Route path={ROUTES.SELECT_TRANSACTION} element={<TransactionTypeScreen />} />

      {/* Money Converter Flow */}
      <Route path={ROUTES.MONEY_CONVERTER} element={<ServiceSelectionScreen />} />
      <Route path={ROUTES.REMINDER} element={<ReminderScreen />} />

      {/* Transaction Flow (with :type parameter) */}
      <Route path={ROUTES.SELECT_AMOUNT} element={<SelectAmountScreen />} />
      <Route path={ROUTES.SELECT_DISPENSE} element={<SelectDispenseScreen />} />
      <Route path={ROUTES.TRANSACTION_FEE} element={<TransactionFeeScreen />} />
      <Route path={ROUTES.CONFIRMATION} element={<ConfirmationScreen />} />
      <Route path={ROUTES.INSERT_MONEY} element={<InsertMoneyScreen />} />
      <Route path={ROUTES.TRANSACTION_SUMMARY} element={<TransactionSummaryScreen />} />

      {/* Feedback Screens */}
      <Route path={ROUTES.PROCESSING} element={<ProcessingScreen />} />
      <Route path={ROUTES.SUCCESS} element={<SuccessScreen />} />
      <Route path={ROUTES.WARNING} element={<WarningScreen />} />

      {/* Forex Flow */}
      <Route path={ROUTES.FOREX} element={<ForexServiceSelectionScreen />} />
      <Route path={ROUTES.FOREX_REMINDER} element={<ForexReminderScreen />} />

      {/* Forex Transaction Flow (with :type parameter) */}
      <Route path={ROUTES.FOREX_RATE} element={<ExchangeRateScreen />} />
      <Route path={ROUTES.FOREX_CONFIRM} element={<ForexConfirmationScreen />} />
      <Route path={ROUTES.FOREX_INSERT} element={<ForexInsertMoneyScreen />} />
      <Route path={ROUTES.FOREX_CONVERSION} element={<ForexConversionScreen />} />
      <Route path={ROUTES.FOREX_SUMMARY} element={<ForexSummaryScreen />} />

      {/* Forex Feedback Screens */}
      <Route path={ROUTES.FOREX_PROCESSING} element={<ForexProcessingScreen />} />
      <Route path={ROUTES.FOREX_SUCCESS} element={<ForexSuccessScreen />} />
      <Route path={ROUTES.FOREX_WARNING} element={<ForexWarningScreen />} />
    </Routes>
  );
}
