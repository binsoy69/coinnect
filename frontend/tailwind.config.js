/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Primary orange palette
        "coinnect-primary": "#F97316",
        "coinnect-primary-dark": "#EA580C",
        "coinnect-primary-light": "#FB923C",

        // Navy for initial screen
        "coinnect-navy": "#0E151F",
        "coinnect-navy-dark": "#0E151F",

        // Status colors
        "coinnect-success": "#22C55E",
        "coinnect-warning": "#84CC16",
        "coinnect-error": "#EF4444",

        // Service card colors
        "coinnect-forex": "#DC2626",
        "coinnect-converter": "#F97316",
        "coinnect-ewallet": "#3B82F6",

        // Surface colors
        "surface-light": "#F3F4F6",
        "surface-white": "#FFFFFF",
        "surface-gray": "#E5E7EB",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "20px",
        button: "9999px",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.5s ease-in-out",
        "slide-up": "slideUp 0.5s ease-out",
        "slide-in-right": "slideInRight 0.3s ease-out",
        "slide-out-left": "slideOutLeft 0.3s ease-out",
        "bounce-dots": "bounceDots 1.4s infinite ease-in-out both",
        "check-draw": "checkDraw 0.5s ease-out forwards",
        float: "float 3s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { transform: "translateY(20px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        slideInRight: {
          "0%": { transform: "translateX(50px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        slideOutLeft: {
          "0%": { transform: "translateX(0)", opacity: "1" },
          "100%": { transform: "translateX(-50px)", opacity: "0" },
        },
        bounceDots: {
          "0%, 80%, 100%": { transform: "scale(0)" },
          "40%": { transform: "scale(1)" },
        },
        checkDraw: {
          "0%": { strokeDashoffset: "100" },
          "100%": { strokeDashoffset: "0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
      },
    },
  },
  plugins: [],
};
