# Coinnect UI/UX Implementation Roadmap

This document serves as the detailed checklist for Phase 1 UI/UX implementation. It follows the mockup designs provided in the `UI/` folder.

**Technology Stack:**

- **Framework**: React 19 + Vite 7
- **Styling**: TailwindCSS (Light Theme with Orange Accents)
- **Animations**: Framer Motion
- **Icons**: Lucide React
- **Routing**: React Router DOM

---

## Design System

### Color Palette

| Token                   | Hex       | Usage                            |
| ----------------------- | --------- | -------------------------------- |
| `coinnect-primary`      | `#F97316` | Primary orange, buttons, accents |
| `coinnect-primary-dark` | `#EA580C` | Hover states                     |
| `coinnect-navy`         | `#1E3A5F` | Initial screen background        |
| `coinnect-navy-dark`    | `#0F2744` | Gradient dark                    |
| `success`               | `#22C55E` | Success states, checkmarks       |
| `warning`               | `#84CC16` | Warning states                   |
| `error`                 | `#EF4444` | Error states                     |
| `forex`                 | `#DC2626` | Foreign Exchange card            |
| `converter`             | `#F97316` | Money Converter card             |
| `ewallet`               | `#3B82F6` | E-Wallet card                    |
| `surface-light`         | `#F3F4F6` | Page backgrounds                 |
| `surface-white`         | `#FFFFFF` | Cards, modals                    |

### Typography

- **Font Family**: Inter (system fallback: sans-serif)
- **Headings**: Bold, 32-48px
- **Body**: Regular, 18-20px
- **Buttons**: Semibold, 20-24px

### Spacing & Sizing

- **Card Border Radius**: 20px
- **Button Border Radius**: Full (pill shape)
- **Page Padding**: 32px
- **Grid Gaps**: 20-24px
- **Touch Targets**: Minimum 48px (primary actions: 64-80px)

---

## File Structure

```
frontend/src/
├── main.jsx
├── App.jsx
├── index.css
│
├── components/
│   ├── common/
│   │   ├── Button.jsx
│   │   ├── Card.jsx
│   │   ├── Header.jsx
│   │   ├── Clock.jsx
│   │   ├── Timer.jsx
│   │   ├── LoadingDots.jsx
│   │   ├── VirtualKeypad.jsx
│   │   └── LoadingSpinner.jsx
│   │
│   ├── layout/
│   │   ├── PageLayout.jsx
│   │   ├── SponsorPanel.jsx
│   │   └── PageTransition.jsx
│   │
│   ├── transaction/
│   │   ├── DenominationGrid.jsx
│   │   ├── DenominationCheckbox.jsx
│   │   ├── MoneyCounter.jsx
│   │   ├── TransactionCard.jsx
│   │   ├── ServiceCard.jsx
│   │   └── InsertMoneyPanel.jsx
│   │
│   ├── feedback/
│   │   ├── SuccessIcon.jsx
│   │   └── WarningIcon.jsx
│   │
│   ├── forex/
│   │   ├── ExchangeRateCard.jsx
│   │   ├── CurrencyAmountGrid.jsx
│   │   └── ConversionDisplay.jsx
│   │
│   └── ewallet/
│       ├── TransactionFeeTable.jsx
│       ├── QRCodeDisplay.jsx
│       ├── AccountDetailsPanel.jsx
│       └── EWalletTransactionCard.jsx
│
├── pages/
│   ├── InitialScreen.jsx
│   ├── TransactionTypeScreen.jsx
│   │
│   ├── money-converter/
│   │   ├── ServiceSelectionScreen.jsx
│   │   ├── ReminderScreen.jsx
│   │   ├── SelectAmountScreen.jsx
│   │   ├── ConfirmationScreen.jsx
│   │   ├── InsertMoneyScreen.jsx
│   │   ├── TransactionFeeScreen.jsx
│   │   ├── SelectDispenseScreen.jsx
│   │   ├── TransactionSummaryScreen.jsx
│   │   ├── ProcessingScreen.jsx
│   │   ├── SuccessScreen.jsx
│   │   └── WarningScreen.jsx
│   │
│   ├── forex/
│   │   ├── ForexServiceSelectionScreen.jsx
│   │   ├── ForexReminderScreen.jsx
│   │   ├── ExchangeRateScreen.jsx
│   │   ├── ForexConfirmationScreen.jsx
│   │   ├── ForexInsertMoneyScreen.jsx
│   │   ├── ForexConversionScreen.jsx
│   │   ├── ForexSummaryScreen.jsx
│   │   ├── ForexProcessingScreen.jsx
│   │   ├── ForexSuccessScreen.jsx
│   │   └── ForexWarningScreen.jsx
│   │
│   └── ewallet/
│       ├── EWalletProviderScreen.jsx
│       ├── EWalletServiceScreen.jsx
│       ├── EWalletReminderScreen.jsx
│       ├── EWalletFeeScreen.jsx
│       ├── EWalletMobileScreen.jsx
│       ├── EWalletAmountScreen.jsx
│       ├── EWalletConfirmScreen.jsx
│       ├── EWalletInsertBillsScreen.jsx
│       ├── EWalletInsertCoinsScreen.jsx
│       ├── EWalletAccountDetailsScreen.jsx
│       ├── EWalletQRCodeScreen.jsx
│       ├── EWalletVerifyPINScreen.jsx
│       ├── EWalletProcessingScreen.jsx
│       ├── EWalletSummaryScreen.jsx
│       └── EWalletSuccessScreen.jsx
│
├── routes/
│   └── index.jsx
│
├── constants/
│   ├── routes.js
│   ├── denominations.js
│   ├── mockData.js
│   ├── forexData.js
│   └── ewalletData.js
│
├── context/
│   ├── TransactionContext.jsx
│   ├── ForexContext.jsx
│   └── EWalletContext.jsx
│
└── hooks/
    └── useCountdown.js
```

---

## Route Structure

| Route                               | Screen                   | Description                   |
| ----------------------------------- | ------------------------ | ----------------------------- |
| `/`                                 | InitialScreen            | Attract/home screen           |
| `/select-transaction`               | TransactionTypeScreen    | Choose transaction type       |
| `/money-converter`                  | ServiceSelectionScreen   | Choose conversion type        |
| `/money-converter/reminder`         | ReminderScreen           | Disclaimer before transaction |
| `/money-converter/:type/amount`     | SelectAmountScreen       | Select denomination           |
| `/money-converter/:type/confirm`    | ConfirmationScreen       | Confirm amount and fee        |
| `/money-converter/:type/insert`     | InsertMoneyScreen        | Insert money interface        |
| `/money-converter/:type/fee`        | TransactionFeeScreen     | Fee payment prompt            |
| `/money-converter/:type/dispense`   | SelectDispenseScreen     | Select dispense denominations |
| `/money-converter/:type/summary`    | TransactionSummaryScreen | Review transaction            |
| `/money-converter/:type/processing` | ProcessingScreen         | Loading animation             |
| `/money-converter/:type/success`    | SuccessScreen            | Transaction complete          |
| `/money-converter/:type/warning`    | WarningScreen            | Amount mismatch warning       |

**Service Types**: `bill-to-bill`, `bill-to-coin`, `coin-to-bill`

### Forex Routes

| Route                     | Screen                      | Description                  |
| ------------------------- | --------------------------- | ---------------------------- |
| `/forex`                  | ForexServiceSelectionScreen | Select exchange direction    |
| `/forex/reminder`         | ForexReminderScreen         | Red disclaimer screen        |
| `/forex/:type/rate`       | ExchangeRateScreen          | Live rate + amount selection |
| `/forex/:type/confirm`    | ForexConfirmationScreen     | Confirm conversion details   |
| `/forex/:type/insert`     | ForexInsertMoneyScreen      | Insert foreign/PHP bills     |
| `/forex/:type/conversion` | ForexConversionScreen       | Show live conversion result  |
| `/forex/:type/summary`    | ForexSummaryScreen          | Transaction review card      |
| `/forex/:type/processing` | ForexProcessingScreen       | Loading animation            |
| `/forex/:type/success`    | ForexSuccessScreen          | Success with checkmark       |
| `/forex/:type/warning`    | ForexWarningScreen          | Amount mismatch              |

**Forex Service Types**: `usd-to-php`, `php-to-usd`, `eur-to-php`, `php-to-eur`

### E-Wallet Routes

| Route                            | Screen                      | Description                    |
| -------------------------------- | --------------------------- | ------------------------------ |
| `/ewallet`                       | EWalletProviderScreen       | Select GCash or Maya           |
| `/ewallet/:provider/service`     | EWalletServiceScreen        | Select Cash In or Cash Out     |
| `/ewallet/reminder`              | EWalletReminderScreen       | Blue disclaimer screen         |
| `/ewallet/:type/fee`             | EWalletFeeScreen            | Transaction fee tiers display  |
| `/ewallet/:type/mobile`          | EWalletMobileScreen         | Enter mobile number            |
| `/ewallet/:type/amount`          | EWalletAmountScreen         | Enter amount with keypad       |
| `/ewallet/:type/confirm`         | EWalletConfirmScreen        | Confirm transaction details    |
| `/ewallet/:type/insert-bills`    | EWalletInsertBillsScreen    | Insert bills (Cash In only)    |
| `/ewallet/:type/insert-coins`    | EWalletInsertCoinsScreen    | Insert coins (Cash In only)    |
| `/ewallet/:type/details`         | EWalletAccountDetailsScreen | Account details review         |
| `/ewallet/:type/qr`              | EWalletQRCodeScreen         | QR code scan (Cash Out only)   |
| `/ewallet/:type/verify`          | EWalletVerifyPINScreen      | Verification PIN (Cash Out)    |
| `/ewallet/:type/processing`      | EWalletProcessingScreen     | Checking spinner               |
| `/ewallet/:type/summary`         | EWalletSummaryScreen        | Transaction summary card       |
| `/ewallet/:type/success`         | EWalletSuccessScreen        | Success with checkmark         |

**E-Wallet Service Types**: `gcash-cash-in`, `gcash-cash-out`, `maya-cash-in`, `maya-cash-out`

---

## ✅ Phase 1.1: Foundation Setup

- [x] **Install Dependencies**
  - [x] Run `npm install react-router-dom`
- [x] **Update TailwindCSS Configuration**
  - [x] Replace dark theme colors with light theme palette
  - [x] Add custom border radius (`card: 20px`)
  - [x] Add animation keyframes
  - [x] **File**: `frontend/tailwind.config.js`
- [x] **Update Global Styles**
  - [x] Set light gray body background
  - [x] Remove dark theme utilities (`.glass`, `.glass-dark`)
  - [x] Add new utility classes
  - [x] **File**: `frontend/src/index.css`
- [x] **Update HTML Title**
  - [x] Change title to "Coinnect"
  - [x] **File**: `frontend/index.html`
- [x] **Setup Router**
  - [x] Create route constants
  - [x] Configure BrowserRouter
  - [x] **Files**: `frontend/src/routes/index.jsx`, `frontend/src/main.jsx`

**Test**: `npm run lint` passes, app loads without errors ✅

---

## ✅ Phase 1.2: Core Components

- [x] **Button Component**
  - [x] Variants: `primary` (orange), `secondary` (outline), `ghost`
  - [x] Sizes: `sm`, `md`, `lg`, `xl`
  - [x] Pill shape with Framer Motion press animation
  - [x] **File**: `frontend/src/components/common/Button.jsx`
- [x] **Card Component**
  - [x] Variants: `default` (white), `orange`, `outlined`
  - [x] 20px border radius
  - [x] **File**: `frontend/src/components/common/Card.jsx`
- [x] **Header Component**
  - [x] Back button (optional)
  - [x] Title display
  - [x] Clock display (optional)
  - [x] **File**: `frontend/src/components/common/Header.jsx`
- [x] **Clock Component**
  - [x] Time format: `HH:MM AM/PM`
  - [x] Date format: `Day | MM.DD.YY`
  - [x] **File**: `frontend/src/components/common/Clock.jsx`
- [x] **Timer Component**
  - [x] Countdown display in seconds
  - [x] Progress bar visualization
  - [x] **File**: `frontend/src/components/common/Timer.jsx`
- [x] **PageLayout Component**
  - [x] Standard page wrapper with padding
  - [x] **File**: `frontend/src/components/layout/PageLayout.jsx`
- [x] **PageTransition Component**
  - [x] Framer Motion AnimatePresence wrapper
  - [x] Slide + fade transitions
  - [x] **File**: `frontend/src/components/layout/PageTransition.jsx`

**Test**: Visual check of each component in isolation ✅

---

## ✅ Phase 1.3: Initial Flow Screens

- [x] **Initial Screen (Attract Mode)**
  - [x] Dark navy gradient background
  - [x] Coinnect logo (placeholder until asset provided)
  - [x] "Simplifying your financial transaction!" tagline
  - [x] "Start Transaction" button
  - [x] Clock in bottom-left corner
  - [x] Sponsor panel on right side
  - [x] Navigation: Button → `/select-transaction`
  - [x] **File**: `frontend/src/pages/InitialScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Initial.png`
- [x] **Transaction Type Screen**
  - [x] Light gray background
  - [x] "Hello! Select Type of Transaction" heading
  - [x] Three service cards:
    - [x] Foreign Exchange (red) - disabled
    - [x] Coin and Bill Converter (orange) - active
    - [x] E-Wallet (blue) - disabled
  - [x] Navigation: Converter card → `/money-converter`
  - [x] **File**: `frontend/src/pages/TransactionTypeScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Type Of Transaction.png`
- [x] **Service Selection Screen**
  - [x] Header with "Coin and Bill Converter" breadcrumb
  - [x] "Select Type of Service" heading
  - [x] Three orange service cards:
    - [x] Coin-to-Bill
    - [x] Bill-to-Coin
    - [x] Bill-to-Bill
  - [x] Navigation: Each card → `/money-converter/reminder`
  - [x] **File**: `frontend/src/pages/money-converter/ServiceSelectionScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Select Service.png`
- [x] **Reminder Screen**
  - [x] Full orange background
  - [x] Kiosk icon with smiley face
  - [x] Disclaimer text about refund policy
  - [x] "Proceed" button
  - [x] Navigation: Button → `/money-converter/:type/amount`
  - [x] **File**: `frontend/src/pages/money-converter/ReminderScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Select Service-1.png`

**Test**: Navigate through Initial → Transaction Type → Service Selection → Reminder ✅

---

## ✅ Phase 1.4: Transaction Components

- [x] **ServiceCard Component**
  - [x] Icon, title, color props
  - [x] Hover scale animation
  - [x] **File**: `frontend/src/components/transaction/ServiceCard.jsx`
- [x] **DenominationGrid Component**
  - [x] Grid of denomination buttons (20, 50, 100, 200, 500, 1000)
  - [x] Single selection state
  - [x] Selected state styling (orange fill)
  - [x] **File**: `frontend/src/components/transaction/DenominationGrid.jsx`
- [x] **DenominationCheckbox Component**
  - [x] Grid with checkbox selection
  - [x] Multi-select support
  - [x] **File**: `frontend/src/components/transaction/DenominationCheckbox.jsx`
- [x] **MoneyCounter Component**
  - [x] Denomination label
  - [x] Count display (`P20 = 2x`)
  - [x] **File**: `frontend/src/components/transaction/MoneyCounter.jsx`
- [x] **TransactionCard Component**
  - [x] Orange background card
  - [x] Transaction type, service type labels
  - [x] Money inserted, total due, money to dispense values
  - [x] Selected denominations display
  - [x] **File**: `frontend/src/components/transaction/TransactionCard.jsx`
- [x] **InsertMoneyPanel Component**
  - [x] Note card with instructions
  - [x] Bill/coin insertion icons
  - [x] **File**: `frontend/src/components/transaction/InsertMoneyPanel.jsx`

**Test**: Visual check of each component ✅

---

## ✅ Phase 1.5: Transaction Flow Screens (Bill-to-Bill)

- [x] **Select Amount Screen**
  - [x] Header with back navigation
  - [x] "Select Your Transaction" heading
  - [x] 6 denomination buttons (20, 50, 100, 200, 500, 1000)
  - [x] "Proceed" button
  - [x] Navigation: Button → `/money-converter/bill-to-bill/dispense`
  - [x] **File**: `frontend/src/pages/money-converter/SelectAmountScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Bill2Bill-3.png`
- [x] **Select Dispense Denomination Screen**
  - [x] Left panel: Money inserted, transaction fee, date/time
  - [x] Right panel: Checkbox grid for denominations
  - [x] "Proceed" button
  - [x] Navigation: Button → `/money-converter/bill-to-bill/fee`
  - [x] **File**: `frontend/src/pages/money-converter/SelectDispenseScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Bill2Bill-4.png`
- [x] **Transaction Fee Prompt Screen**
  - [x] Orange background
  - [x] "Would you like to insert transaction fee?" question
  - [x] "No" and "Yes" buttons
  - [x] Navigation: Either → `/money-converter/bill-to-bill/confirm`
  - [x] **File**: `frontend/src/pages/money-converter/TransactionFeeScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Bill2Bill-5.png`
- [x] **Confirmation Screen**
  - [x] Orange background
  - [x] Amount selected, transaction fee, total due
  - [x] "Back" and "Proceed" buttons
  - [x] Navigation: Proceed → `/money-converter/bill-to-bill/insert`
  - [x] **File**: `frontend/src/pages/money-converter/ConfirmationScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Bill2Bill-6.png`
- [x] **Insert Money Screen**
  - [x] Header with conversion type indicator
  - [x] Left panel: Note with instruction, bill/coin insertion icon
  - [x] Right panel: "Please Insert Bill/Coins" heading
  - [x] Current count display
  - [x] Denomination counters (P20 = 0x, P50 = 0x, etc.)
  - [x] Timer with progress bar (60s countdown)
  - [x] Auto-close warning text
  - [x] **File**: `frontend/src/pages/money-converter/InsertMoneyScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Bill2Bill.png`, `Bill2Bill-1.png`
- [x] **Transaction Summary Screen**
  - [x] Orange TransactionCard centered
  - [x] All transaction details
  - [x] "Back" and "Proceed" buttons
  - [x] Navigation: Proceed → `/money-converter/bill-to-bill/processing`
  - [x] **File**: `frontend/src/pages/money-converter/TransactionSummaryScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Bill2Bill-2.png`

**Test**: Navigate through complete Bill-to-Bill flow ✅

---

## ✅ Phase 1.6: Feedback Screens

- [x] **LoadingDots Component**
  - [x] 5 white dots with bounce animation
  - [x] Staggered animation timing
  - [x] **File**: `frontend/src/components/common/LoadingDots.jsx`
- [x] **SuccessIcon Component**
  - [x] Green circle background
  - [x] Animated checkmark (draw animation)
  - [x] **File**: `frontend/src/components/feedback/SuccessIcon.jsx`
- [x] **WarningIcon Component**
  - [x] Yellow-green circle background
  - [x] Exclamation mark icon
  - [x] **File**: `frontend/src/components/feedback/WarningIcon.jsx`
- [x] **Processing Screen**
  - [x] Orange background
  - [x] LoadingDots animation centered
  - [x] "Dispensing Money" / "Please wait..." text
  - [x] Auto-advance after 2 seconds → Success screen
  - [x] **File**: `frontend/src/pages/money-converter/ProcessingScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Coin2Bill-6.png`
- [x] **Success Screen**
  - [x] Orange background
  - [x] Animated green checkmark
  - [x] "Successfully dispensed the money!" message
  - [x] "Check the money dispenser and receipt." instruction
  - [x] "Exit" button → `/`
  - [x] "Another Transaction" button → `/select-transaction`
  - [x] **File**: `frontend/src/pages/money-converter/SuccessScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Bill2Bill-7.png`
- [x] **Warning Screen**
  - [x] Orange background
  - [x] Yellow-green warning icon
  - [x] "The total amount you inserted does not match the selected transaction."
  - [x] "Insert More Money" button
  - [x] **File**: `frontend/src/pages/money-converter/WarningScreen.jsx`
  - [x] **Mockup**: `UI/money-converter/Coin2Bill-3.png`

**Test**: Navigate to Processing → Success, check animations ✅

---

## ✅ Phase 1.7: Bill-to-Coin & Coin-to-Bill Flows

- [x] **Bill-to-Coin Flow**
  - [x] Reuse same screens with different mock data
  - [x] Amount options: 20, 50, 100, 200
  - [x] Dispense denominations: 1, 5, 10, 20 (coins)
  - [x] **Mockups**: `UI/money-converter/Bill2Coin*.png`
- [x] **Coin-to-Bill Flow**
  - [x] Reuse same screens with different mock data
  - [x] Amount options: 20, 50, 100, 200
  - [x] Dispense denominations: 20, 50, 100, 200 (bills)
  - [x] **Mockups**: `UI/money-converter/Coin2Bill*.png`

**Test**: Navigate through all three conversion flows ✅

---

## ✅ Phase 1.8: Polish & Animations

- [x] **Page Transitions**
  - [x] Add AnimatePresence to all route changes
  - [x] Slide-in from right, slide-out to left
- [x] **Button Animations**
  - [x] Press scale effect (0.98)
  - [x] Hover brightness change
- [x] **Card Animations**
  - [x] Hover lift effect (translateY -4px)
  - [x] Selection pulse
- [x] **Logo Animation**
  - [x] Subtle floating animation on Initial screen
- [x] **Sponsor Panel**
  - [x] Add placeholder for sponsor logos
  - [x] Pagination dots at bottom

**Test**: Visual inspection of all animations, smooth transitions ✅

---

## Phase 1.9: Forex Flow

_Goal: Add Foreign Exchange UI flow with red theme (#DC2626) following mockups in `UI/forex/`._

### Forex Design System Additions

| Token                 | Hex       | Usage                             |
| --------------------- | --------- | --------------------------------- |
| `coinnect-forex`      | `#DC2626` | Forex cards, backgrounds, accents |
| `coinnect-forex-dark` | `#B91C1C` | Forex hover states                |

### Forex Currency Denominations

| Currency | Accept                            | Dispense                          |
| -------- | --------------------------------- | --------------------------------- |
| **USD**  | $10, $50, $100                    | $10, $50, $100                    |
| **EUR**  | €5, €10, €20                      | €5, €10, €20                      |
| **PHP**  | P20, P50, P100, P200, P500, P1000 | P20, P50, P100, P200, P500, P1000 |

### Phase 1.9.1: Forex Foundation

- [x] **Create Forex Routes**
  - [x] Add forex route constants to `routes.js`
  - [x] Register forex routes in router
  - [x] **File**: `frontend/src/constants/routes.js`
- [x] **Create Forex Constants**
  - [x] Service types: `usd-to-php`, `php-to-usd`, `eur-to-php`, `php-to-eur`
  - [x] Currency configs with flags, denominations, fee percentages
  - [x] Mock exchange rates
  - [x] **File**: `frontend/src/constants/forexData.js`
- [x] **Create ForexContext**
  - [x] State: serviceType, currencies, exchangeRate, rateLocked, amounts, fees
  - [x] Functions: startForexTransaction, lockRate, setSelectedAmount, etc.
  - [x] **File**: `frontend/src/context/ForexContext.jsx`

**Test**: Context provides correct config for each forex service type

---

### Phase 1.9.2: Forex Components

- [x] **ExchangeRateCard Component**
  - [x] Display: Flag | Country Name | Currency Code | Rate in PHP
  - [x] Red background with white text
  - [x] "Rate changes every 60 seconds" notice
  - [x] **File**: `frontend/src/components/forex/ExchangeRateCard.jsx`
- [x] **CurrencyAmountGrid Component**
  - [x] Grid of currency amount buttons (€5, €10, €20 or $10, $50, $100)
  - [x] Single selection with red border when selected
  - [x] Currency symbol prefix display
  - [x] **File**: `frontend/src/components/forex/CurrencyAmountGrid.jsx`
- [x] **ConversionDisplay Component**
  - [x] Table format: Amount | From | To
  - [x] Shows conversion calculation
  - [x] Note about centavos not included
  - [x] **File**: `frontend/src/components/forex/ConversionDisplay.jsx`

**Test**: Visual check of each forex component in isolation

---

### Phase 1.9.3: Forex Screens

- [x] **Forex Service Selection Screen**
  - [x] Header with "Foreign Exchange" breadcrumb
  - [x] "Select Type of Service" heading
  - [x] Four red service cards:
    - [x] USD-to-PHP (US flag icon)
    - [x] PHP-to-USD (PH flag icon)
    - [x] EUR-to-PHP (EU flag icon)
    - [x] PHP-to-EUR (PH flag icon)
  - [x] Navigation: Each card → `/forex/reminder`
  - [x] **File**: `frontend/src/pages/forex/ForexServiceSelectionScreen.jsx`
  - [x] **Mockup**: `UI/forex/Select Service.png`
- [x] **Forex Reminder Screen**
  - [x] Full red background
  - [x] Kiosk icon with smiley face
  - [x] Same disclaimer text as money converter
  - [x] "Proceed" button
  - [x] Navigation: Button → `/forex/:type/rate`
  - [x] **File**: `frontend/src/pages/forex/ForexReminderScreen.jsx`
  - [x] **Mockup**: `UI/forex/Select Service-1.png`
- [x] **Exchange Rate Screen**
  - [x] Header with back navigation
  - [x] "Live Foreign Currency Exchange Rates" heading
  - [x] "\*This rate changes every 60 seconds" notice
  - [x] ExchangeRateCard showing current rate
  - [x] "Select Specific Amount" / "Select [Currency] to Dispense" label
  - [x] CurrencyAmountGrid for amount selection
  - [x] "Proceed" button
  - [x] Navigation: Button → `/forex/:type/confirm`
  - [x] **File**: `frontend/src/pages/forex/ExchangeRateScreen.jsx`
  - [x] **Mockups**: `UI/forex/EURtoPHP.png`, `UI/forex/PHPtoEUR.png`, etc.
- [x] **Forex Confirmation Screen**
  - [x] Full red background
  - [x] Question mark icon in circle
  - [x] Display: Amount Selected | Amount Converted | Transaction Fee | Amount to Dispense
  - [x] "Click Proceed to Continue" instruction
  - [x] Note: "Transaction fee automatically deducted from inserted amount"
  - [x] "Back" and "Proceed" buttons
  - [x] **Rate locks on this screen**
  - [x] Navigation: Proceed → `/forex/:type/insert`
  - [x] **File**: `frontend/src/pages/forex/ForexConfirmationScreen.jsx`
  - [x] **Mockup**: `UI/forex/EURtoPHP-1.png`
- [x] **Forex Insert Money Screen**
  - [x] Header with "[Currency]-to-[Currency] Conversion" indicator
  - [x] Left panel: Note with instructions, bill insertion icon
  - [x] Right panel: "Please Insert [Currency] Bill" heading
  - [x] Accepted denominations in parentheses
  - [x] Current count display
  - [x] Total Due badge
  - [x] Denomination counters (e.g., €5 = 1x, €10 = 0x)
  - [x] Timer with progress bar (60s countdown)
  - [x] Auto-close warning text
  - [x] Navigation: Timer complete or amount matched → `/forex/:type/conversion`
  - [x] **File**: `frontend/src/pages/forex/ForexInsertMoneyScreen.jsx`
  - [x] **Mockups**: `UI/forex/EURtoPHP-2.png`, `UI/forex/PHPtoEUR-2.png`
- [x] **Forex Conversion Screen**
  - [x] Header with conversion type indicator
  - [x] Left panel (red card): Money Inserted, Transaction Fee, DateTime
  - [x] Right panel:
    - [x] "Live [Currency] Currency Exchange Rates" heading
    - [x] ExchangeRateCard
    - [x] "Conversion (Transaction Fee not included)" label
    - [x] ConversionDisplay table
  - [x] "Proceed" button
  - [x] Navigation: Button → `/forex/:type/summary`
  - [x] **File**: `frontend/src/pages/forex/ForexConversionScreen.jsx`
  - [x] **Mockups**: `UI/forex/EURtoPHP-3.png`, `UI/forex/PHPtoEUR-3.png`
- [x] **Forex Summary Screen**
  - [x] Red TransactionCard centered
  - [x] "MY TRANSACTION" header
  - [x] Transaction Type: "Foreign Exchange"
  - [x] Service Type: "[Currency]-to-[Currency]"
  - [x] Total Money Inserted (in source currency)
  - [x] Converted Amount (in target currency)
  - [x] Transaction Fee (in PHP)
  - [x] Money to Dispensed (in target currency)
  - [x] "Back" and "Proceed" buttons
  - [x] Navigation: Proceed → `/forex/:type/processing`
  - [x] **File**: `frontend/src/pages/forex/ForexSummaryScreen.jsx`
  - [x] **Mockups**: `UI/forex/EURtoPHP-4.png`, `UI/forex/PHPtoEUR-4.png`
- [x] **Forex Processing Screen**
  - [x] Full red background
  - [x] LoadingDots animation (white dots)
  - [x] "Dispensing Money" / "Please wait..." text
  - [x] Auto-advance after 2.5s → Success screen
  - [x] **File**: `frontend/src/pages/forex/ForexProcessingScreen.jsx`
  - [x] **Mockup**: `UI/forex/EURtoPHP-5.png`
- [x] **Forex Success Screen**
  - [x] Full red background
  - [x] Animated green checkmark (SuccessIcon)
  - [x] "Successfully dispensed excess money!" message
  - [x] "Check the cash tray." instruction
  - [x] "Proceed" button
  - [x] Navigation: Proceed → additional success or exit options
  - [x] **File**: `frontend/src/pages/forex/ForexSuccessScreen.jsx`
  - [x] **Mockups**: `UI/forex/EURtoPHP-9.png` through `EURtoPHP-12.png`
- [x] **Forex Warning Screen**
  - [x] Full red background
  - [x] Yellow warning icon
  - [x] "The total amount you inserted does not match the selected transaction."
  - [x] "Choose a Different Amount" and "Insert More Money" buttons
  - [x] **File**: `frontend/src/pages/forex/ForexWarningScreen.jsx`
  - [x] **Mockup**: `UI/forex/Information Message1.png`

**Test**: Navigate through complete forex flow for each service type

---

### Phase 1.9.4: Flow Integration

- [x] **Enable Forex on Transaction Type Screen**
  - [x] Remove `disabled` prop from Foreign Exchange card
  - [x] Add onClick navigation to `/forex`
  - [x] **File**: `frontend/src/pages/TransactionTypeScreen.jsx`
- [x] **Test All Forex Flows**
  - [x] USD-to-PHP: Complete flow with timer and success
  - [x] PHP-to-USD: Complete flow with PHP insertion
  - [x] EUR-to-PHP: Complete flow
  - [x] PHP-to-EUR: Complete flow
- [x] **Verify Visual Consistency**
  - [x] Red theme applied consistently
  - [x] Animations match money converter quality
  - [x] Back navigation works on all screens

**Test**: Full E2E testing of all 4 forex flows ✅

---

## Phase 1.10: E-Wallet Flow

_Goal: Add E-Wallet (GCash + Maya) Cash In / Cash Out UI flow with blue theme (#3B82F6) following mockups in `UI/e-wallet/`._

### E-Wallet Design System Additions

| Token                    | Hex       | Usage                              |
| ------------------------ | --------- | ---------------------------------- |
| `coinnect-ewallet`       | `#3B82F6` | E-Wallet cards, backgrounds, accents |
| `coinnect-ewallet-dark`  | `#2563EB` | E-Wallet hover states              |

### E-Wallet Providers

| Provider  | Services                | Icon                        |
| --------- | ----------------------- | --------------------------- |
| **GCash** | Cash In, Cash Out       | GCash logo (blue)           |
| **Maya**  | Cash In, Cash Out       | Maya logo (blue)            |

### E-Wallet Fee Structure

| Amount Range  | Transaction Fee |
| ------------- | --------------- |
| P1 - P500     | P15             |
| P501 - P1000  | P25             |

Fee is automatically deducted from the inserted amount.

### E-Wallet Bill/Coin Denominations

| Type      | Denominations                        |
| --------- | ------------------------------------ |
| **Bills** | P20, P50, P100, P200, P500, P1000   |
| **Coins** | P1, P5, P10, P20                     |

### Phase 1.10.1: E-Wallet Foundation

- [x] **Create E-Wallet Routes**
  - [x] Add e-wallet route constants to `routes.js`
  - [x] Add `getEWalletRoute()` helper function
  - [x] Register e-wallet routes in router
  - [x] **File**: `frontend/src/constants/routes.js`, `frontend/src/routes/index.jsx`
- [x] **Create E-Wallet Constants**
  - [x] Provider configs: GCash, Maya
  - [x] Service types: `gcash-cash-in`, `gcash-cash-out`, `maya-cash-in`, `maya-cash-out`
  - [x] Fee tiers: P1-P500 = P15, P501-P1000 = P25
  - [x] Bill denominations: P20, P50, P100, P200, P500, P1000
  - [x] Coin denominations: P1, P5, P10, P20
  - [x] Mock data for all 4 service types
  - [x] Helper functions: `calculateFee()`, `getEWalletConfig()`, `isCashIn()`, `isCashOut()`
  - [x] **File**: `frontend/src/constants/ewalletData.js`
- [x] **Create EWalletContext**
  - [x] State: provider, serviceType, mobileNumber, amount, fee, totalDue, insertedBills, insertedCoins, billerNumber
  - [x] Functions: startEWalletTransaction, setMobileNumber, setAmount, addInsertedBill, addInsertedCoin, resetTransaction
  - [x] Helper: isAmountMatched, getTotalInserted, getRemainingAmount
  - [x] **File**: `frontend/src/context/EWalletContext.jsx`

**Test**: Context provides correct config for each e-wallet service type ✅

---

### Phase 1.10.2: New Shared Components

- [x] **VirtualKeypad Component**
  - [x] 3x4 number grid (1-9, empty, 0, backspace)
  - [x] Input display field with blue border
  - [x] Configurable maxLength (11 for mobile, 4 for amount, 6 for PIN)
  - [x] Configurable placeholder text
  - [x] onSubmit callback
  - [x] Framer Motion press animations on keys
  - [x] **File**: `frontend/src/components/common/VirtualKeypad.jsx`
- [x] **LoadingSpinner Component**
  - [x] 8 dots arranged in circle
  - [x] Rotation animation (spinning)
  - [x] Dots vary in size (larger at top, smaller at bottom)
  - [x] White dots on blue background
  - [x] Customizable text below (default: "Checking...")
  - [x] **File**: `frontend/src/components/common/LoadingSpinner.jsx`
- [x] **Update InsertMoneyPanel**
  - [x] Add `ewallet` cardVariant (blue color scheme)
  - [x] **File**: `frontend/src/components/transaction/InsertMoneyPanel.jsx`

**Test**: Visual check of VirtualKeypad and LoadingSpinner in isolation ✅

---

### Phase 1.10.3: E-Wallet Components

- [x] **TransactionFeeTable Component**
  - [x] Table with Amount and Transaction Fee columns
  - [x] Blue background rows for fee tiers
  - [x] Note text: "The transaction fee is automatically deducted from the inserted amount."
  - [x] Optional extra note for Cash Out
  - [x] **File**: `frontend/src/components/ewallet/TransactionFeeTable.jsx`
- [x] **QRCodeDisplay Component**
  - [x] Static QR code placeholder image
  - [x] Provider name in heading: "Scan QR Code (GCash App)" / "(Maya App)"
  - [x] Instruction text: "Scan QR Code and input money you want to send."
  - [x] "After paying, click the button" text
  - [x] "Verify Transaction" button
  - [x] **File**: `frontend/src/components/ewallet/QRCodeDisplay.jsx`
- [x] **AccountDetailsPanel Component**
  - [x] Two-column layout
  - [x] Left: Blue summary card (Money Inserted/Send, Transaction Fee, DateTime)
  - [x] Right: Account Details (Biller, Mobile Number, Amount to Transfer)
  - [x] Proceed button
  - [x] **File**: `frontend/src/components/ewallet/AccountDetailsPanel.jsx`
- [x] **EWalletTransactionCard Component**
  - [x] Blue background card (matching blue theme)
  - [x] "MY TRANSACTION" header with subtitle
  - [x] Fields: Transaction Type, Service Type, Mobile Number, Total Money Inserted, Transaction Fee, Money to Transfer, Total Due
  - [x] Back and Proceed buttons
  - [x] **File**: `frontend/src/components/ewallet/EWalletTransactionCard.jsx`

**Test**: Visual check of each e-wallet component in isolation ✅

---

### Phase 1.10.4: E-Wallet Entry Screens

- [x] **E-Wallet Provider Screen**
  - [x] Header with "E-Wallet" breadcrumb
  - [x] "Select your E-Wallet" heading
  - [x] Two blue service cards: GCash, Maya
  - [x] Navigation: Each card → `/ewallet/:provider/service`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletProviderScreen.jsx`
  - [x] **Mockup**: `UI/e-wallet/Select Service.png`
- [x] **E-Wallet Service Screen**
  - [x] Header with provider name breadcrumb (e.g., "GCash")
  - [x] "Select Type of Service" heading
  - [x] Two blue service cards: Cash In (down arrow), Cash Out (up arrow)
  - [x] Provider-specific icons (GCash logo with arrows, Maya logo with arrows)
  - [x] Navigation: Each card → `/ewallet/reminder`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletServiceScreen.jsx`
  - [x] **Mockups**: `UI/e-wallet/GCASH CASH IN.png`, `UI/e-wallet/MAYA CASH IN.png`
- [x] **E-Wallet Reminder Screen**
  - [x] Full blue background
  - [x] Kiosk icon with smiley face
  - [x] Same disclaimer text as money converter/forex
  - [x] "Proceed" button
  - [x] Navigation: Button → `/ewallet/:type/fee`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletReminderScreen.jsx`
  - [x] **Mockup**: `UI/e-wallet/Select Service-1.png`

**Test**: Navigate through E-Wallet Provider → Service → Reminder ✅

---

### Phase 1.10.5: Cash In Screens

- [x] **E-Wallet Fee Screen**
  - [x] Header with service indicator (e.g., "E-Wallet / GCash Cash In" + icon)
  - [x] "Transaction Fee" heading
  - [x] TransactionFeeTable component
  - [x] Note: "The transaction fee is automatically deducted from the inserted amount."
  - [x] Cash Out extra note: "Ensure you have your mobile phone and the provided mobile number with you."
  - [x] "Proceed" button
  - [x] Navigation: Button → `/ewallet/:type/mobile`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletFeeScreen.jsx`
  - [x] **Mockup**: `UI/e-wallet/GCASH CASH IN-2.png`
- [x] **E-Wallet Mobile Number Screen**
  - [x] Header with service indicator
  - [x] "Enter Mobile Number" heading
  - [x] VirtualKeypad (maxLength: 11)
  - [x] "Proceed" button
  - [x] Navigation: Button → `/ewallet/:type/amount`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletMobileScreen.jsx`
  - [x] **Mockup**: `UI/e-wallet/GCASH CASH IN-3.png`
- [x] **E-Wallet Amount Screen**
  - [x] Header with service indicator
  - [x] "Enter Amount" heading
  - [x] VirtualKeypad (maxLength: 4)
  - [x] "Pay" button
  - [x] Navigation: Button → `/ewallet/:type/confirm`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletAmountScreen.jsx`
  - [x] **Mockup**: `UI/e-wallet/GCASH CASH IN-4.png`
- [x] **E-Wallet Confirm Screen**
  - [x] Full blue background
  - [x] Question mark icon in circle
  - [x] Display: Mobile Number | Amount to Transfer | Transaction Fee | Total Due
  - [x] "Click Proceed to Continue" instruction
  - [x] "Back" and "Proceed" buttons
  - [x] Navigation: Proceed → `/ewallet/:type/insert-bills` (Cash In) or `/ewallet/:type/qr` (Cash Out)
  - [x] **File**: `frontend/src/pages/ewallet/EWalletConfirmScreen.jsx`
  - [x] **Mockup**: `UI/e-wallet/GCASH CASH IN-5.png`
- [x] **E-Wallet Insert Bills Screen**
  - [x] Header with service indicator
  - [x] Left panel: InsertMoneyPanel (bill variant, ewallet cardVariant)
  - [x] Right panel: "Please Insert Money" heading
  - [x] Current count display + Total Due badge
  - [x] Bill denomination counters (P20-P1000)
  - [x] Timer with progress bar (60s countdown)
  - [x] Auto-close warning text
  - [x] If bills >= totalDue: auto-proceed to Account Details
  - [x] If bills < totalDue: show "Insert Coins" option
  - [x] Navigation: Amount matched → `/ewallet/:type/details`, need coins → `/ewallet/:type/insert-coins`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletInsertBillsScreen.jsx`
  - [x] **Mockup**: `UI/e-wallet/GCASH CASH IN-6.png`
- [x] **E-Wallet Insert Coins Screen**
  - [x] Same layout as Insert Bills but with coin denominations
  - [x] Coin denomination counters (P1, P5, P10, P20)
  - [x] Shows remaining amount needed after bills
  - [x] Timer with progress bar (60s countdown)
  - [x] If total (bills + coins) >= totalDue: auto-proceed
  - [x] Navigation: Amount matched → `/ewallet/:type/details`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletInsertCoinsScreen.jsx`

**Test**: Navigate through complete Cash In flow with bill/coin insertion ✅

---

### Phase 1.10.6: Cash Out Screens

- [x] **E-Wallet QR Code Screen**
  - [x] Header with service indicator
  - [x] "Scan QR Code (GCash/Maya App)" heading
  - [x] "Scan QR Code and input money you want to send." instruction
  - [x] Static QR code placeholder image
  - [x] "After paying, click the button" text
  - [x] "Verify Transaction" button
  - [x] Navigation: Button → `/ewallet/:type/verify`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletQRCodeScreen.jsx`
  - [x] **Mockup**: `UI/e-wallet/GCASH CASH OUT-3.png`
- [x] **E-Wallet Verify PIN Screen**
  - [x] Header with service indicator
  - [x] "Enter Verification PIN" heading
  - [x] "We send Verification PIN to your mobile number." subtitle
  - [x] VirtualKeypad (maxLength: 6)
  - [x] "Proceed" button (accepts any input)
  - [x] Navigation: Button → `/ewallet/:type/details`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletVerifyPINScreen.jsx`
  - [x] **Mockup**: `UI/e-wallet/GCASH CASH OUT-4.png`

**Test**: Navigate through QR Code → Verify PIN → Account Details ✅

---

### Phase 1.10.7: Shared End Screens

- [x] **E-Wallet Account Details Screen**
  - [x] Header with service indicator
  - [x] AccountDetailsPanel component
  - [x] Left blue card: Money Inserted/Send, Transaction Fee, DateTime
  - [x] Right: Account Details (Biller, Mobile Number, Amount to Transfer)
  - [x] "Proceed" button
  - [x] Navigation: Button → `/ewallet/:type/processing`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletAccountDetailsScreen.jsx`
  - [x] **Mockups**: `UI/e-wallet/GCASH CASH IN-7.png`, `UI/e-wallet/GCASH CASH OUT-5.png`
- [x] **E-Wallet Processing Screen**
  - [x] Full blue background
  - [x] LoadingSpinner animation (circular dots)
  - [x] "Checking..." text
  - [x] Auto-advance after 2.5s → Summary screen
  - [x] **File**: `frontend/src/pages/ewallet/EWalletProcessingScreen.jsx`
  - [x] **Mockup**: `UI/e-wallet/GCASH CASH IN-8.png`
- [x] **E-Wallet Summary Screen**
  - [x] EWalletTransactionCard centered
  - [x] "MY TRANSACTION" header
  - [x] Transaction Type: "E-Wallet"
  - [x] Service Type: "GCash Cash In" / "Maya Cash Out" etc.
  - [x] Mobile Number
  - [x] Total Money Inserted, Transaction Fee, Money to Transfer, Total Due
  - [x] "Back" and "Proceed" buttons
  - [x] Navigation: Proceed → `/ewallet/:type/success`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletSummaryScreen.jsx`
  - [x] **Mockups**: `UI/e-wallet/GCASH CASH IN-9.png`, `UI/e-wallet/GCASH CASH OUT-8.png`
- [x] **E-Wallet Success Screen**
  - [x] Full blue background
  - [x] Animated green checkmark (SuccessIcon)
  - [x] Cash In: "Successfully transfer the money! Get the receipt."
  - [x] Cash Out: "Successfully dispensed the money! Check the cash tray and receipt!"
  - [x] "Exit" button → `/`
  - [x] "Another Transaction" button → `/select-transaction`
  - [x] **File**: `frontend/src/pages/ewallet/EWalletSuccessScreen.jsx`
  - [x] **Mockups**: `UI/e-wallet/GCASH CASH IN-10.png`, `UI/e-wallet/GCASH CASH OUT-9.png`

**Test**: Navigate through Account Details → Processing → Summary → Success ✅

---

### Phase 1.10.8: Flow Integration

- [x] **Enable E-Wallet on Transaction Type Screen**
  - [x] Set `enabled: true` for E-Wallet card
  - [x] Add onClick navigation to `/ewallet`
  - [x] **File**: `frontend/src/pages/TransactionTypeScreen.jsx`
- [x] **Test All E-Wallet Flows**
  - [x] GCash Cash In: Complete flow with bill/coin insertion
  - [x] GCash Cash Out: Complete flow with QR + PIN verification
  - [x] Maya Cash In: Complete flow with bill/coin insertion
  - [x] Maya Cash Out: Complete flow with QR + PIN verification
- [x] **Verify Visual Consistency**
  - [x] Blue theme applied consistently
  - [x] Animations match money converter/forex quality
  - [x] Back navigation works on all screens
  - [x] VirtualKeypad works correctly on all input screens

**Test**: Full E2E testing of all 4 e-wallet flows ✅

---

## E-Wallet Mock Data Reference

```javascript
// Fee tiers (same for all providers)
const EWALLET_FEE_TIERS = [
  { min: 1, max: 500, fee: 15 },
  { min: 501, max: 1000, fee: 25 },
];

// Static values for navigation demo
const EWALLET_MOCK_DATA = {
  "gcash-cash-in": {
    mobileNumber: "09924456533",
    amount: 105,           // total due
    transferAmount: 90,    // amount to e-wallet
    fee: 15,               // transaction fee
    billerNumber: "09099242851",
  },
  "gcash-cash-out": {
    mobileNumber: "09924456533",
    amount: 1025,          // total due
    dispenseAmount: 1000,  // cash to dispense
    fee: 25,               // transaction fee
    billerNumber: "09099242851",
  },
  "maya-cash-in": {
    mobileNumber: "09924456533",
    amount: 105,
    transferAmount: 90,
    fee: 15,
    billerNumber: "09099242851",
  },
  "maya-cash-out": {
    mobileNumber: "09924456533",
    amount: 105,
    dispenseAmount: 90,
    fee: 15,
    billerNumber: "09099242851",
  },
};
```

---

## Forex Mock Data Reference

```javascript
// Exchange rates (mock values for demo)
const FOREX_RATES = {
  USD: 58.7656, // 1 USD = 58.7656 PHP
  EUR: 61.7246, // 1 EUR = 61.7246 PHP
};

// Fee percentage
const FOREX_FEE_PERCENTAGE = 5; // 5% transaction fee

// Static values for navigation demo
const FOREX_MOCK_DATA = {
  "usd-to-php": {
    rate: 58.7656,
    selectedAmount: 5, // $5 USD
    convertedAmount: 293, // PHP equivalent
    feePercentage: 5,
    feeAmount: 30, // P30 fee
    amountToDispense: 263, // P263 to dispense
  },
  "php-to-usd": {
    rate: 0.017, // 1 PHP = 0.017 USD
    selectedAmount: 5, // $5 USD to receive
    convertedAmount: 294, // PHP needed
    feePercentage: 5,
    feeAmount: 30,
    totalDue: 324, // P324 to insert
  },
  "eur-to-php": {
    rate: 61.7246,
    selectedAmount: 5, // €5 EUR
    convertedAmount: 308, // PHP equivalent
    feePercentage: 5,
    feeAmount: 15,
    amountToDispense: 293, // P293 to dispense
  },
  "php-to-eur": {
    rate: 0.0162, // 1 PHP = 0.0162 EUR
    selectedAmount: 5, // €5 EUR to receive
    convertedAmount: 308, // PHP needed
    feePercentage: 5,
    feeAmount: 15,
    totalDue: 323, // P323 to insert
  },
};
```

---

## Mock Data Reference

```javascript
// Static values for navigation demo
const MOCK_DATA = {
  billToBill: {
    selectedAmount: 100,
    fee: 10,
    totalDue: 110,
    moneyInserted: 110,
    dispenseDenominations: [20, 50],
    moneyToDispense: 100,
  },
  billToCoin: {
    selectedAmount: 200,
    fee: 15,
    totalDue: 215,
    moneyInserted: 200,
    dispenseDenominations: [1, 5, 10, 20],
    moneyToDispense: 185,
  },
  coinToBill: {
    selectedAmount: 20,
    fee: 3,
    totalDue: 23,
    moneyInserted: 23,
    dispenseDenominations: [20],
    moneyToDispense: 20,
  },
};
```

---

## ✅ Testing Checklist

**Money Converter Navigation Flows:**

- [x] Initial → Transaction Type → Service Selection → Reminder → Amount → Dispense → Fee → Confirm → Insert → Summary → Processing → Success → Exit (Home)
- [x] Initial → ... → Success → Another Transaction → Transaction Type
- [x] Back button works on every screen with header
- [x] Warning screen → Insert More Money → Insert Money screen

**Forex Navigation Flows:**

- [ ] Initial → Transaction Type → Forex Service Selection → Reminder → Rate → Confirm → Insert → Conversion → Summary → Processing → Success
- [ ] All 4 forex service types complete flow (USD↔PHP, EUR↔PHP)
- [ ] Back button works on all forex screens
- [ ] Warning screen → Choose Different Amount / Insert More Money
- [ ] Rate locks on confirmation screen

**E-Wallet Navigation Flows:**

- [x] Initial → Transaction Type → E-Wallet Provider → Service Selection → Reminder → Fee → Mobile → Amount → Confirm → Insert Bills → [Insert Coins] → Account Details → Processing → Summary → Success
- [x] Cash Out: ... → Confirm → QR Code → Verify PIN → Account Details → Processing → Summary → Success
- [x] All 4 e-wallet service types complete flow (GCash/Maya Cash In/Out)
- [x] Back button works on all e-wallet screens
- [x] Bill/coin split insertion works (bills first, optional coins)
- [x] VirtualKeypad works correctly on mobile, amount, and PIN screens
- [x] Exit → Home, Another Transaction → Transaction Type

**Linting:**

- [x] `npm run lint` passes with no errors

**Visual:**

- [x] Colors match mockups (orange for converter)
- [x] Colors match mockups (red for forex)
- [x] Colors match mockups (blue for e-wallet)
- [x] Typography matches mockups
- [x] Spacing and layout match mockups
- [x] Animations are smooth (60fps)

---

## Assets Required

- [x] **Coinnect Logo** - PNG files in `public/assets/`
- [ ] **Sponsor Logos** - Optional, for sponsor panel (user to provide)
- [x] **E-Wallet Provider Icons** - GCash/Maya Cash In/Out icons in `public/assets/`
- [ ] **QR Code Placeholder Images** - Static QR images for GCash/Maya Cash Out screens

---

## Dependencies

```bash
npm install react-router-dom
```

All other dependencies (Framer Motion, Lucide React, TailwindCSS) are already installed.
