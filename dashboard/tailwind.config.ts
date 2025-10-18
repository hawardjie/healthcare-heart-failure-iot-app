import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'hf-blue': '#0ea5e9',
        'hf-red': '#ef4444',
        'hf-green': '#10b981',
        'hf-yellow': '#f59e0b',
      },
    },
  },
  plugins: [],
}
export default config
