import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Realm colors
        realm: {
          assess: {
            DEFAULT: "#ef4444",
            light: "#fca5a5",
            dark: "#dc2626",
          },
          decide: {
            DEFAULT: "#f59e0b",
            light: "#fcd34d",
            dark: "#d97706",
          },
          do: {
            DEFAULT: "#22c55e",
            light: "#86efac",
            dark: "#16a34a",
          },
        },
        // UI colors
        background: "var(--background)",
        foreground: "var(--foreground)",
        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",
        border: "var(--border)",
        primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",
      },
    },
  },
  plugins: [],
};

export default config;
