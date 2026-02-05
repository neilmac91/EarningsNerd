const { fontFamily } = require('tailwindcss/defaultTheme')

const mintColors = {
  50: '#ECFDF5',
  100: '#D1FAE5',
  200: '#A7F3D0',
  300: '#6EE7B7',
  400: '#34D399',
  500: '#10B981', // Main accent
  600: '#059669',
  700: '#047857',
  800: '#065F46',
  900: '#064E3B',
}

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Core Palette
        background: {
          light: '#FFFFFF', // White
          dark: '#111827', // gray-900
        },
        panel: {
          light: '#F9FAFB', // gray-50
          dark: '#1F2937', // gray-800
        },
        // Accent Color
        mint: mintColors,
        // Alias primary to mint for backward compatibility
        primary: mintColors,
        // Text Palette
        text: {
          primary: {
            light: '#111827', // gray-900
            dark: '#FFFFFF',
          },
          secondary: {
            light: '#374151', // gray-700
            dark: '#9CA3AF', // gray-400
          },
          tertiary: {
            light: '#6B7280', // gray-500
            dark: '#4B5563', // gray-600
          },
        },
        // Universal Border
        border: {
          light: '#E5E7EB', // gray-200
          dark: '#374151', // gray-700
        }
      },
      fontFamily: {
        sans: ['var(--font-inter)', ...fontFamily.sans],
      },
      backgroundImage: {
        'hero-gradient': 'linear-gradient(to bottom right, #0B1120, #111827, #1a1147)',
        'hero-glow': 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(16, 185, 129, 0.12), transparent)',
        'cta-gradient': 'linear-gradient(135deg, #064E3B, #0f172a, #1e1b4b)',
      },
      boxShadow: {
        'glow-mint': '0 0 40px -10px rgba(16, 185, 129, 0.3)',
        'glow-mint-sm': '0 0 20px -5px rgba(16, 185, 129, 0.2)',
        'glow-mint-lg': '0 0 60px -15px rgba(16, 185, 129, 0.25)',
      },
      keyframes: {
        shimmer: {
          '100%': {
            transform: 'translateX(100%)',
          },
        },
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'count-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        shimmer: 'shimmer 2s infinite',
        'fade-up': 'fade-up 0.6s ease-out forwards',
        'fade-up-delay-1': 'fade-up 0.6s ease-out 0.1s forwards',
        'fade-up-delay-2': 'fade-up 0.6s ease-out 0.2s forwards',
        'fade-up-delay-3': 'fade-up 0.6s ease-out 0.3s forwards',
        'count-up': 'count-up 0.4s ease-out forwards',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
