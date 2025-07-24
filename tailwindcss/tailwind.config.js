/** @type {import('tailwindcss').Config} */
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
//        'primary-hover': '#cbd5e1',
        'primary-hover': '#94a2b7',
        danger: '#ef4444',
        success: '#22c55e',
        warning: '#f59e0b',
        info: '#3b82f6',
      },
    },
  },
  plugins: [],
};
