/* file: web/tailwind.config.ts */
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          fg: "#000000",
          text: "#545454",
          bg: "#E6E3E4",
          bg2: "#E5DFD2"
        }
      },
      fontFamily: {
        sans: ["Poppins", "ui-sans-serif", "system-ui"]
      },
      borderRadius: {
        xl: "1rem",
        "2xl": "1.25rem"
      }
    }
  },
  plugins: []
};
export default config;
