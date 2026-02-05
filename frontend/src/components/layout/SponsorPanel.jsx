import { useState } from 'react';

export default function SponsorPanel({ className = '' }) {
  const [activeIndex, setActiveIndex] = useState(0);

  // Placeholder sponsor slots
  const sponsors = [
    { id: 1, name: 'Sponsor 1' },
    { id: 2, name: 'Sponsor 2' },
    { id: 3, name: 'Sponsor 3' },
  ];

  return (
    <div className={`flex flex-col items-center ${className}`}>
      {/* Sponsor display area */}
      <div className="bg-white/10 backdrop-blur-sm rounded-card p-6 w-full aspect-[3/4] flex flex-col items-center justify-center mb-4">
        {/* Placeholder sponsor logos */}
        <div className="space-y-4 w-full">
          {sponsors.map((sponsor, index) => (
            <div
              key={sponsor.id}
              className={`
                bg-white/20 rounded-lg p-4 text-center text-white/60 text-sm
                ${index === activeIndex ? 'ring-2 ring-white/40' : ''}
              `}
            >
              {sponsor.name}
            </div>
          ))}
        </div>
      </div>

      {/* Pagination dots */}
      <div className="flex gap-2">
        {sponsors.map((_, index) => (
          <button
            key={index}
            onClick={() => setActiveIndex(index)}
            className={`
              w-2 h-2 rounded-full transition-all
              ${index === activeIndex ? 'bg-white w-6' : 'bg-white/40'}
            `}
          />
        ))}
      </div>
    </div>
  );
}
