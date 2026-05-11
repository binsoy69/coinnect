/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        'coinnect-primary': '#F97316',
        'coinnect-primary-dark': '#EA580C',
        'coinnect-navy': '#0E151F',
        'coinnect-navy-soft': '#172231',
        'coinnect-success': '#22C55E',
        'coinnect-warning': '#F59E0B',
        'coinnect-error': '#EF4444',
        'surface-light': '#F3F4F6',
        'surface-white': '#FFFFFF',
        'surface-gray': '#E5E7EB',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        card: '20px',
        button: '9999px',
      },
      boxShadow: {
        panel: '0 24px 60px rgba(15, 23, 42, 0.12)',
      },
    },
  },
  plugins: [],
};
