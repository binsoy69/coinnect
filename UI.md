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
│   │   └── LoadingDots.jsx
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
│   └── forex/
│       ├── ExchangeRateCard.jsx
│       ├── CurrencyAmountGrid.jsx
│       └── ConversionDisplay.jsx
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
│   └── forex/
│       ├── ForexServiceSelectionScreen.jsx
│       ├── ForexReminderScreen.jsx
│       ├── ExchangeRateScreen.jsx
│       ├── ForexConfirmationScreen.jsx
│       ├── ForexInsertMoneyScreen.jsx
│       ├── ForexConversionScreen.jsx
│       ├── ForexSummaryScreen.jsx
│       ├── ForexProcessingScreen.jsx
│       ├── ForexSuccessScreen.jsx
│       └── ForexWarningScreen.jsx
│
├── routes/
│   └── index.jsx
│
├── constants/
│   ├── routes.js
│   ├── denominations.js
│   ├── mockData.js
│   └── forexData.js
│
├── context/
│   ├── TransactionContext.jsx
│   └── ForexContext.jsx
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
- [ ] **Test All Forex Flows**
  - [ ] USD-to-PHP: Complete flow with timer and success
  - [ ] PHP-to-USD: Complete flow with PHP insertion
  - [ ] EUR-to-PHP: Complete flow
  - [ ] PHP-to-EUR: Complete flow
- [ ] **Verify Visual Consistency**
  - [ ] Red theme applied consistently
  - [ ] Animations match money converter quality
  - [ ] Back navigation works on all screens

**Test**: Full E2E testing of all 4 forex flows ✅

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

**Linting:**

- [x] `npm run lint` passes with no errors

**Visual:**

- [x] Colors match mockups (orange for converter)
- [ ] Colors match mockups (red for forex)
- [x] Typography matches mockups
- [x] Spacing and layout match mockups
- [x] Animations are smooth (60fps)

---

## Assets Required

- [x] **Coinnect Logo** - PNG files in `public/assets/`
- [ ] **Sponsor Logos** - Optional, for sponsor panel (user to provide)

---

## Dependencies

```bash
npm install react-router-dom
```

All other dependencies (Framer Motion, Lucide React, TailwindCSS) are already installed.
