import type { Config } from "tailwindcss";

/**
 * Ledger design system → Tailwind. Colors/fonts/radius/shadows resolve to the
 * CSS variables defined in app/globals.css, so `bg-surface`, `text-ink-900`,
 * `font-display`, `rounded-lg`, `shadow-lg`, etc. all map to the tokens.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)",
        surface: "var(--surface)",
        "surface-sunken": "var(--surface-sunken)",
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
        "line-faint": "var(--line-faint)",
        ink: {
          900: "var(--ink-900)",
          800: "var(--ink-800)",
          700: "var(--ink-700)",
          600: "var(--ink-600)",
          500: "var(--ink-500)",
          400: "var(--ink-400)",
          300: "var(--ink-300)",
        },
        violet: {
          700: "var(--violet-700)",
          600: "var(--violet-600)",
          500: "var(--violet-500)",
          100: "var(--violet-100)",
          50: "var(--violet-50)",
        },
        coral: {
          700: "var(--coral-700)",
          600: "var(--coral-600)",
          500: "var(--coral-500)",
          100: "var(--coral-100)",
          50: "var(--coral-50)",
        },
        teal: {
          700: "var(--teal-700)",
          600: "var(--teal-600)",
          500: "var(--teal-500)",
          100: "var(--teal-100)",
          50: "var(--teal-50)",
        },
        amber: {
          700: "var(--amber-700)",
          600: "var(--amber-600)",
          500: "var(--amber-500)",
          100: "var(--amber-100)",
          50: "var(--amber-50)",
        },
        sky: {
          700: "var(--sky-700)",
          600: "var(--sky-600)",
          500: "var(--sky-500)",
          100: "var(--sky-100)",
          50: "var(--sky-50)",
        },
        lime: {
          700: "var(--lime-700)",
          600: "var(--lime-600)",
          500: "var(--lime-500)",
          100: "var(--lime-100)",
          50: "var(--lime-50)",
        },
        success: {
          600: "var(--success-600)",
          500: "var(--success-500)",
          100: "var(--success-100)",
        },
        warning: {
          600: "var(--warning-600)",
          500: "var(--warning-500)",
          100: "var(--warning-100)",
        },
        danger: {
          600: "var(--danger-600)",
          500: "var(--danger-500)",
          100: "var(--danger-100)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        pill: "var(--radius-pill)",
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        xl: "var(--shadow-xl)",
        brand: "var(--shadow-brand)",
        hairline: "var(--elevation-hairline)",
      },
    },
  },
  plugins: [],
};

export default config;
