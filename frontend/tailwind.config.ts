import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Brand palette ported from ui/styles.css
        brand: {
          dark:    "#2C3E50",
          mid:     "#4A6FA5",
          light:   "#C5D8F0",
          beige:   "#F5F0EB",
          stone:   "#D4C9B8",
          muted:   "#8A7F74",
          success: "#5A8A5A",
          warning: "#C8A951",
          danger:  "#C0392B",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
