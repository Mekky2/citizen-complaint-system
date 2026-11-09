/** @type {import('tailwindcss').Config} */
// Look & feel ported from the original Citizen Portal prototype:
// slate-900 canvas, slate-800/80 cards with slate-700 borders, blue-600 primary, tinted status chips.
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Theme-aware neutral scale: dark = real slate, light = inverted (see src/index.css).
        slate: {
          50: 'rgb(var(--s-50) / <alpha-value>)',
          100: 'rgb(var(--s-100) / <alpha-value>)',
          200: 'rgb(var(--s-200) / <alpha-value>)',
          300: 'rgb(var(--s-300) / <alpha-value>)',
          400: 'rgb(var(--s-400) / <alpha-value>)',
          500: 'rgb(var(--s-500) / <alpha-value>)',
          600: 'rgb(var(--s-600) / <alpha-value>)',
          700: 'rgb(var(--s-700) / <alpha-value>)',
          800: 'rgb(var(--s-800) / <alpha-value>)',
          900: 'rgb(var(--s-900) / <alpha-value>)',
          950: 'rgb(var(--s-950) / <alpha-value>)',
        },
      },
      fontFamily: { sans: ['Cairo', 'Tahoma', 'system-ui', 'sans-serif'] },
      keyframes: {
        eqbar: { '0%,100%': { transform: 'scaleY(.25)' }, '50%': { transform: 'scaleY(1)' } },
        pingring: { '0%': { transform: 'scale(1)', opacity: '.7' }, '100%': { transform: 'scale(1.9)', opacity: '0' } },
        rise: { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } },
      },
      animation: {
        eq: 'eqbar .9s ease-in-out infinite',
        ring: 'pingring 1.4s ease-out infinite',
        rise: 'rise .25s ease-out both',
      },
    },
  },
  plugins: [],
};
