/** @type {import('tailwindcss').Config} */
const colors = require('tailwindcss/colors')
module.exports = {
  content: [
    '../templates/**/*.html',
    '../static/js/**/*.js',
  ],
  theme: {
    extend: {
      fontSize: {
        base: '1.1rem',
        lg: '1.25rem',
        xl: '1.5rem',
        '2xl': '2rem',
      },
      colors: {
        primary: '#1e293b',
        'primary-light': '#334155',
        'primary-text': '#f1f5f9',
        'primary-text-hover': '#94A3B8',
        'primary-hover': '#1E3A51',
        danger: colors.red,
        success: colors.green,
        warning: colors.amber,
        info:    colors.slate,
      },
    },
  },
  plugins: [],
};
