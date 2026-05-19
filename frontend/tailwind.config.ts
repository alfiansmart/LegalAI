import type { Config } from "tailwindcss";

export default {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0b0d12",
        foreground: "#e5e7eb",
        accent: "#7c3aed",
      },
    },
  },
  plugins: [],
} satisfies Config;
