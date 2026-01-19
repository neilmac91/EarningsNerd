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
      keyframes: {
        shimmer: {
          '100%': {
            transform: 'translateX(100%)',
          },
        },
      },
      animation: {
        shimmer: 'shimmer 2s infinite',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
