import Card from "../common/Card";

// Accent color mapping for SVG fills per card variant
const accentColors = {
  orange: "#F97316",
  forex: "#DC2626",
  ewallet: "#3B82F6",
  gcash: "#007DFE",
  maya: "#01B463",
};

// Inline SVG for bill insert illustration
const BillInsertIcon = ({ accentColor = "#F97316" }) => (
  <svg
    viewBox="0 0 120 120"
    className="w-32 h-32 mx-auto"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Bill acceptor slot */}
    <rect
      x="30"
      y="70"
      width="60"
      height="10"
      rx="2"
      fill="white"
      fillOpacity="0.3"
    />
    <rect
      x="35"
      y="72"
      width="50"
      height="6"
      rx="1"
      fill="white"
      fillOpacity="0.5"
    />

    {/* Bill being inserted */}
    <rect
      x="40"
      y="20"
      width="40"
      height="55"
      rx="3"
      fill="white"
      fillOpacity="0.9"
    />
    <rect
      x="45"
      y="25"
      width="30"
      height="8"
      rx="1"
      fill={accentColor}
      fillOpacity="0.5"
    />
    <rect
      x="45"
      y="38"
      width="20"
      height="3"
      rx="1"
      fill={accentColor}
      fillOpacity="0.3"
    />
    <rect
      x="45"
      y="45"
      width="25"
      height="3"
      rx="1"
      fill={accentColor}
      fillOpacity="0.3"
    />

    {/* Arrow indicating insertion direction */}
    <path
      d="M60 85 L60 95 M55 90 L60 95 L65 90"
      stroke="white"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

// Inline SVG for coin insert illustration
const CoinInsertIcon = ({ accentColor = "#F97316" }) => (
  <svg
    viewBox="0 0 120 120"
    className="w-32 h-32 mx-auto"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Coin slot */}
    <rect
      x="45"
      y="80"
      width="30"
      height="8"
      rx="4"
      fill="white"
      fillOpacity="0.3"
    />
    <rect
      x="50"
      y="82"
      width="20"
      height="4"
      rx="2"
      fill="white"
      fillOpacity="0.5"
    />

    {/* Coins being inserted */}
    <circle cx="60" cy="35" r="18" fill="white" fillOpacity="0.9" />
    <circle cx="60" cy="35" r="14" fill={accentColor} fillOpacity="0.3" />
    <text
      x="60"
      y="40"
      textAnchor="middle"
      fill="white"
      fontSize="12"
      fontWeight="bold"
    >
      ₱
    </text>

    <circle cx="45" cy="55" r="12" fill="white" fillOpacity="0.7" />
    <circle cx="45" cy="55" r="9" fill={accentColor} fillOpacity="0.3" />

    <circle cx="75" cy="55" r="12" fill="white" fillOpacity="0.7" />
    <circle cx="75" cy="55" r="9" fill={accentColor} fillOpacity="0.3" />

    {/* Arrow indicating insertion direction */}
    <path
      d="M60 95 L60 105 M55 100 L60 105 L65 100"
      stroke="white"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export default function InsertMoneyPanel({
  variant = "bill", // 'bill' or 'coin'
  cardVariant = "orange", // 'orange' or 'forex'
  noteText = "",
  className = "",
}) {
  return (
    <Card
      variant={cardVariant}
      animated={false}
      className={`p-4 flex flex-col items-center text-center h-full justify-center ${className}`}
    >
      {/* Note label */}
      <div className="mb-4">
        <span className="text-2xl font-bold text-white uppercase tracking-wider">
          NOTE
        </span>
      </div>

      {/* Instruction text */}
      <p className="text-white text-xl font-semibold mb-6 leading-tight max-w-[200px]">
        {noteText}
      </p>

      {/* Insert illustration */}
      <div className="mt-auto mb-4">
        {variant === "coin" ? (
          <CoinInsertIcon
            accentColor={accentColors[cardVariant] || accentColors.orange}
          />
        ) : (
          <BillInsertIcon
            accentColor={accentColors[cardVariant] || accentColors.orange}
          />
        )}
      </div>
    </Card>
  );
}
