import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        sumi: "var(--sumi)",
        char: "var(--char)",
        slate: "var(--slate)",
        ash: "var(--ash)",
        smoke: "var(--smoke)",
        fog: "var(--fog)",
        mist: "var(--mist)",
        haze: "var(--haze)",
        bone: "var(--bone)",
        paper: "var(--paper)",
        line: "var(--line)",
        "line-strong": "var(--line-strong)"
      },
      fontFamily: {
        sans: ["var(--sans)"],
        serif: ["var(--font-mincho)", "serif"],
        display: ["var(--font-archivo)", "var(--sans)"]
      },
      borderRadius: {
        none: "0",
        DEFAULT: "0"
      },
      maxWidth: {
        wrap: "var(--wrap)"
      }
    }
  },
  plugins: []
};

export default config;
