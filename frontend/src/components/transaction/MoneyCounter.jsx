import { DENOMINATION_DISPLAY } from '../../constants/denominations';

export default function MoneyCounter({
  counts = {},
  denominations = [],
  variant = 'horizontal',
  className = '',
}) {
  // If no denominations provided, use keys from counts
  const denoms = denominations.length > 0
    ? denominations
    : Object.keys(counts).map(Number).sort((a, b) => a - b);

  if (variant === 'vertical') {
    return (
      <div className={`flex flex-col gap-2 ${className}`}>
        {denoms.map((denom) => {
          const count = counts[denom] || 0;
          const hasCount = count > 0;

          return (
            <div
              key={denom}
              className={`
                flex justify-between items-center py-2 px-4 rounded-lg
                ${hasCount ? 'bg-coinnect-primary/10' : 'bg-gray-100'}
              `}
            >
              <span className={`font-semibold ${hasCount ? 'text-coinnect-primary' : 'text-gray-600'}`}>
                {DENOMINATION_DISPLAY[denom] || `P${denom}`}
              </span>
              <span className={`font-bold ${hasCount ? 'text-coinnect-primary' : 'text-gray-400'}`}>
                {count}x
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  // Horizontal variant
  return (
    <div className={`flex flex-wrap gap-6 justify-center ${className}`}>
      {denoms.map((denom) => {
        const count = counts[denom] || 0;
        const hasCount = count > 0;

        return (
          <div
            key={denom}
            className={`
              text-center px-4 py-2 rounded-lg
              ${hasCount ? 'bg-coinnect-primary/10' : ''}
            `}
          >
            <span className={`font-semibold ${hasCount ? 'text-coinnect-primary' : 'text-gray-600'}`}>
              {DENOMINATION_DISPLAY[denom] || `P${denom}`} = {count}x
            </span>
          </div>
        );
      })}
    </div>
  );
}
