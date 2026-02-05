import { useState, useEffect } from 'react';

export default function Clock({ variant = 'dark', showDate = true, className = '' }) {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // Format time: "1:00PM"
  const formatTime = (date) => {
    let hours = date.getHours();
    const minutes = date.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12; // 0 becomes 12
    const minutesStr = minutes < 10 ? '0' + minutes : minutes;
    return `${hours}:${minutesStr}${ampm}`;
  };

  // Format date: "Monday | 12.07.24"
  const formatDate = (date) => {
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const day = days[date.getDay()];
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const dayNum = String(date.getDate()).padStart(2, '0');
    const year = String(date.getFullYear()).slice(-2);
    return `${day} | ${month}.${dayNum}.${year}`;
  };

  const textColor = variant === 'light' ? 'text-white' : 'text-gray-600';
  const timeColor = variant === 'light' ? 'text-white' : 'text-gray-900';

  return (
    <div className={`text-right ${className}`}>
      <div className={`text-2xl font-bold ${timeColor}`}>
        {formatTime(time)}
      </div>
      {showDate && (
        <div className={`text-sm ${textColor}`}>
          {formatDate(time)}
        </div>
      )}
    </div>
  );
}
